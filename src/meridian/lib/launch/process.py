"""Process management for primary agent launch."""

import fcntl
import json
import logging
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import time
import tty
import struct
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO, cast

from pydantic import BaseModel, ConfigDict

from meridian.lib.config.settings import MeridianConfig, load_config
from meridian.lib.core.spawn_lifecycle import resolve_execution_terminal_state
from meridian.lib.core.types import HarnessId, SpawnId
from meridian.lib.harness.adapter import SubprocessHarness
from meridian.lib.harness.materialize import cleanup_materialized
from meridian.lib.harness.registry import HarnessRegistry
from meridian.lib.ops.session_policy import ensure_session_work_item
from meridian.lib.state import spawn_store
from meridian.lib.state.artifact_store import LocalStore, make_artifact_key
from meridian.lib.state.atomic import atomic_write_text
from meridian.lib.state.paths import resolve_spawn_log_dir, resolve_state_paths
from meridian.lib.state.session_store import start_session, stop_session, update_session_harness_id
from meridian.lib.state.spawn_store import FOREGROUND_LAUNCH_MODE

from .command import build_harness_context, build_launch_env
from .heartbeat import threaded_heartbeat_scope
from .resolve import resolve_primary_session_metadata
from .session_scope import ManagedSession, session_scope
from .session_ids import extract_latest_session_id
from .types import LaunchRequest, PrimarySessionMetadata, build_primary_prompt

logger = logging.getLogger(__name__)
_PRIMARY_OUTPUT_FILENAME = "output.jsonl"


def active_primary_lock_path(repo_root: Path) -> Path:
    """Return the active primary-session lock path."""

    return resolve_state_paths(repo_root).active_primary_lock


class LaunchContext(BaseModel):
    """Resolved configuration for one primary launch."""

    model_config = ConfigDict(frozen=True)

    config: MeridianConfig
    prompt: str
    session_metadata: PrimarySessionMetadata
    state_root: Path
    lock_path: Path
    seed_harness_session_id: str
    command_request: LaunchRequest


class ProcessOutcome(BaseModel):
    """Result of running the harness subprocess."""

    model_config = ConfigDict(frozen=True)

    command: tuple[str, ...]
    exit_code: int
    chat_id: str | None
    primary_spawn_id: str | None
    primary_started: float
    primary_started_epoch: float
    primary_started_local_iso: str | None
    resolved_harness_session_id: str


def _primary_launch_lock_payload(
    *,
    command: tuple[str, ...],
    child_pid: int | None,
) -> dict[str, object]:
    return {
        "parent_pid": os.getpid(),
        "child_pid": child_pid,
        "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": list(command),
    }


def _rewrite_primary_launch_lock_payload(handle: TextIO, payload: dict[str, object]) -> None:
    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


@contextmanager
def primary_launch_lock(lock_path: Path, payload: dict[str, object]) -> Iterator[TextIO]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("A primary launch is already active.") from exc
        _rewrite_primary_launch_lock_payload(handle, payload)
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def cleanup_orphaned_locks(repo_root: Path) -> bool:
    """Remove a stale active-primary lock."""

    lock_path = active_primary_lock_path(repo_root)
    if not lock_path.is_file():
        return False

    try:
        with lock_path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            try:
                lock_path.unlink(missing_ok=True)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        logger.debug("Failed to inspect lock file %s", lock_path, exc_info=True)
        return False
    return True


def _cleanup_launch_materialized(
    *,
    repo_root: Path,
    harness_id: str,
    harness_registry: HarnessRegistry,
) -> None:
    if not harness_id.strip():
        return
    try:
        cleanup_materialized(harness_id, repo_root, registry=harness_registry)
    except Exception:
        logger.warning(
            "Failed to cleanup primary-session materialized harness resources (harness=%s).",
            harness_id,
            exc_info=True,
        )


def _sweep_orphaned_materializations(
    repo_root: Path,
    harness_id: str,
    *,
    harness_registry: HarnessRegistry,
) -> None:
    """Best-effort sweep of materialized files not owned by active sessions."""

    from meridian.lib.harness.materialize import cleanup_orphaned_materializations
    from meridian.lib.state.session_store import collect_active_chat_ids

    _ = harness_id
    try:
        active_ids = collect_active_chat_ids(repo_root)
        if active_ids is None:
            return
        for known_harness_id in harness_registry.ids():
            adapter = harness_registry.get(known_harness_id)
            if not isinstance(adapter, SubprocessHarness):
                continue
            if adapter.native_layout() is None:
                continue
            cleanup_orphaned_materializations(
                str(known_harness_id),
                repo_root,
                has_active_sessions=bool(active_ids),
                registry=harness_registry,
            )
    except Exception:
        logger.debug("Orphan materialization sweep failed", exc_info=True)


def _copy_primary_pty_output(
    *,
    child_pid: int,
    master_fd: int,
    output_log_path: Path,
) -> int:
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    stdin_open = True
    saved_tty_attrs: Any = None

    output_log_path.parent.mkdir(parents=True, exist_ok=True)
    restore_resize = _install_winsize_forwarding(source_fd=stdout_fd, target_fd=master_fd)
    try:
        if os.isatty(stdin_fd):
            saved_tty_attrs = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)

        with output_log_path.open("wb") as output_handle:
            while True:
                fds = [master_fd]
                if stdin_open:
                    fds.append(stdin_fd)
                ready, _, _ = select.select(fds, [], [])

                if master_fd in ready:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        break
                    output_handle.write(chunk)
                    output_handle.flush()
                    os.write(stdout_fd, chunk)

                if stdin_open and stdin_fd in ready:
                    data = os.read(stdin_fd, 1024)
                    if not data:
                        stdin_open = False
                    else:
                        os.write(master_fd, data)
    finally:
        restore_resize()
        if saved_tty_attrs is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_tty_attrs)

    _, status = os.waitpid(child_pid, 0)
    return os.waitstatus_to_exitcode(status)


def _run_primary_process_with_capture(
    *,
    command: tuple[str, ...],
    cwd: Path,
    env: dict[str, str],
    output_log_path: Path | None,
    on_child_started: Callable[[int], None] | None = None,
) -> tuple[int, int | None]:
    if output_log_path is None or not sys.stdin.isatty() or not sys.stdout.isatty():
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            text=True,
        )
        if on_child_started is not None:
            try:
                on_child_started(process.pid)
            except Exception:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                raise
        try:
            return process.wait(), process.pid
        except KeyboardInterrupt:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                return process.wait(), process.pid
            return 130, process.pid

    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        try:
            os.chdir(cwd)
            os.execvpe(command[0], command, env)
        except FileNotFoundError:
            os._exit(127)
        except Exception:
            os._exit(1)

    try:
        if on_child_started is not None:
            try:
                on_child_started(child_pid)
            except Exception:
                try:
                    os.kill(child_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(child_pid, 0)
                except ChildProcessError:
                    pass
                raise
        _sync_pty_winsize(source_fd=sys.stdout.fileno(), target_fd=master_fd)
        exit_code = _copy_primary_pty_output(
            child_pid=child_pid,
            master_fd=master_fd,
            output_log_path=output_log_path,
        )
        return exit_code, child_pid
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass


def _read_winsize(fd: int) -> bytes | None:
    """Return packed winsize bytes for one terminal fd, or None if unavailable."""

    try:
        return fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
    except OSError:
        return None


def _sync_pty_winsize(*, source_fd: int, target_fd: int) -> None:
    """Copy the current terminal winsize onto the PTY master."""

    winsize = _read_winsize(source_fd)
    if winsize is None:
        return
    try:
        fcntl.ioctl(target_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        return


def _invoke_previous_sigwinch_handler(
    previous: signal.Handlers,
    *,
    signum: int,
    frame: Any,
) -> None:
    if previous in {signal.SIG_DFL, signal.SIG_IGN, None}:
        return
    if callable(previous):
        previous(signum, frame)


def _install_winsize_forwarding(*, source_fd: int, target_fd: int) -> Any:
    """Sync PTY size now and on future terminal resize signals."""

    _sync_pty_winsize(source_fd=source_fd, target_fd=target_fd)
    previous = cast("signal.Handlers", signal.getsignal(signal.SIGWINCH))

    def _handle_resize(signum: int, frame: Any) -> None:
        _sync_pty_winsize(source_fd=source_fd, target_fd=target_fd)
        _invoke_previous_sigwinch_handler(previous, signum=signum, frame=frame)

    signal.signal(signal.SIGWINCH, _handle_resize)

    def _restore() -> None:
        signal.signal(signal.SIGWINCH, previous)

    return _restore


def prepare_launch_context(
    repo_root: Path,
    request: LaunchRequest,
    harness_registry: HarnessRegistry,
) -> LaunchContext:
    """Config loading, prompt building, session-ID seeding, command-request patching."""

    config = load_config(repo_root)
    session_metadata = resolve_primary_session_metadata(
        repo_root=repo_root,
        request=request,
        config=config,
        harness_registry=harness_registry,
    )
    state_root = resolve_state_paths(repo_root).root_dir
    lock_path = active_primary_lock_path(repo_root)

    explicit_session_id = (
        request.continue_harness_session_id.strip()
        if request.continue_harness_session_id is not None
        else ""
    )
    prompt = build_primary_prompt(request)

    adapter = harness_registry.get_subprocess_harness(HarnessId(session_metadata.harness))
    seed = adapter.seed_session(
        is_resume=bool(explicit_session_id),
        harness_session_id=explicit_session_id,
        passthrough_args=request.passthrough_args,
    )
    seed_harness_session_id = seed.session_id
    command_request = request
    if seed.session_args:
        command_request = request.model_copy(
            update={"passthrough_args": (*request.passthrough_args, *seed.session_args)},
        )

    return LaunchContext(
        config=config,
        prompt=prompt,
        session_metadata=session_metadata,
        state_root=state_root,
        lock_path=lock_path,
        seed_harness_session_id=seed_harness_session_id,
        command_request=command_request,
    )


def run_harness_process(
    repo_root: Path,
    request: LaunchRequest,
    ctx: LaunchContext,
    harness_registry: HarnessRegistry,
) -> ProcessOutcome:
    """Start session, spawn tracking, launch process, wait for exit."""

    command: tuple[str, ...] = ()
    chat_id: str | None = None
    primary_spawn_id: SpawnId | None = None
    primary_started = 0.0
    primary_started_epoch = 0.0
    primary_started_local_iso: str | None = None
    resolved_harness_session_id = ctx.seed_harness_session_id
    managed_session: ManagedSession | None = None
    artifacts = LocalStore(root_dir=resolve_state_paths(repo_root).artifacts_dir)

    exit_code = 2
    with primary_launch_lock(
        ctx.lock_path,
        _primary_launch_lock_payload(command=command, child_pid=None),
    ) as lock_handle:
        try:
            _sweep_orphaned_materializations(
                repo_root,
                ctx.session_metadata.harness,
                harness_registry=harness_registry,
            )
            with session_scope(
                state_root=ctx.state_root,
                harness=ctx.session_metadata.harness,
                harness_session_id=ctx.seed_harness_session_id,
                model=ctx.session_metadata.model,
                chat_id=request.continue_chat_id,
                agent=ctx.session_metadata.agent,
                agent_path=ctx.session_metadata.agent_path,
                skills=ctx.session_metadata.skills,
                skill_paths=ctx.session_metadata.skill_paths,
                _start_session=start_session,
                _stop_session=stop_session,
                _update_session_harness_id=update_session_harness_id,
            ) as managed:
                managed_session = managed
                chat_id = managed.chat_id
                ensure_session_work_item(ctx.state_root, chat_id)
                try:
                    primary_spawn_id = spawn_store.start_spawn(
                        ctx.state_root,
                        chat_id=chat_id,
                        model=ctx.session_metadata.model,
                        agent=ctx.session_metadata.agent,
                        harness=ctx.session_metadata.harness,
                        kind="primary",
                        prompt=ctx.prompt,
                        launch_mode=FOREGROUND_LAUNCH_MODE,
                        status="queued",
                    )
                    log_dir = resolve_spawn_log_dir(repo_root, primary_spawn_id)
                    with threaded_heartbeat_scope(log_dir / "heartbeat"):
                        primary_started = time.monotonic()
                        primary_started_epoch = time.time()
                        primary_started_local_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                        harness_context = build_harness_context(
                            repo_root=repo_root,
                            request=ctx.command_request,
                            prompt=ctx.prompt,
                            harness_registry=harness_registry,
                            chat_id=chat_id,
                            config=ctx.config,
                        )
                        command = harness_context.command
                        _rewrite_primary_launch_lock_payload(
                            lock_handle,
                            _primary_launch_lock_payload(command=command, child_pid=None),
                        )
                        child_env = build_launch_env(
                            repo_root,
                            request,
                            chat_id=chat_id,
                            default_autocompact_pct=ctx.config.primary.autocompact_pct,
                            spawn_id=primary_spawn_id,
                            harness_context=harness_context,
                        )
                        output_log_path = log_dir / _PRIMARY_OUTPUT_FILENAME

                        def _record_primary_started(child_pid: int) -> None:
                            _rewrite_primary_launch_lock_payload(
                                lock_handle,
                                _primary_launch_lock_payload(command=command, child_pid=child_pid),
                            )
                            atomic_write_text(
                                log_dir / "harness.pid",
                                f"{child_pid}\n",
                            )
                            spawn_store.mark_spawn_running(
                                ctx.state_root,
                                primary_spawn_id,
                                launch_mode=FOREGROUND_LAUNCH_MODE,
                                worker_pid=child_pid,
                            )

                        exit_code, _child_pid = _run_primary_process_with_capture(
                            command=command,
                            cwd=repo_root,
                            env=child_env,
                            output_log_path=output_log_path,
                            on_child_started=_record_primary_started,
                        )
                        if output_log_path.exists():
                            artifacts.put(
                                make_artifact_key(primary_spawn_id, _PRIMARY_OUTPUT_FILENAME),
                                output_log_path.read_bytes(),
                            )
                finally:
                    status, exit_code, _failure_reason = resolve_execution_terminal_state(
                        exit_code=exit_code,
                        failure_reason=None,
                    )
                    if primary_spawn_id is not None:
                        duration = (
                            max(0.0, time.monotonic() - primary_started)
                            if primary_started > 0.0
                            else None
                        )
                        spawn_store.finalize_spawn(
                            ctx.state_root,
                            primary_spawn_id,
                            status=status,
                            exit_code=exit_code,
                            duration_secs=duration,
                        )
                    observed_harness_session_id = None
                    adapter = harness_registry.get_subprocess_harness(
                        HarnessId(ctx.session_metadata.harness)
                    )
                    if primary_started_epoch > 0.0:
                        observed_harness_session_id = extract_latest_session_id(
                            adapter=adapter,
                            current_session_id=resolved_harness_session_id,
                            artifacts=artifacts,
                            spawn_id=primary_spawn_id,
                            repo_root=repo_root,
                            started_at_epoch=primary_started_epoch,
                            started_at_local_iso=primary_started_local_iso,
                        )
                    if (
                        observed_harness_session_id is not None
                        and observed_harness_session_id.strip()
                        and observed_harness_session_id.strip() != resolved_harness_session_id.strip()
                    ):
                        resolved_harness_session_id = observed_harness_session_id.strip()
                        managed.record_harness_session_id(resolved_harness_session_id)
        except FileNotFoundError:
            logger.debug("Harness command not found", exc_info=True)
            exit_code = 2
        finally:
            if managed_session is not None:
                _cleanup_launch_materialized(
                    repo_root=repo_root,
                    harness_id=ctx.session_metadata.harness,
                    harness_registry=harness_registry,
                )

    return ProcessOutcome(
        command=command,
        exit_code=exit_code,
        chat_id=chat_id,
        primary_spawn_id=primary_spawn_id,
        primary_started=primary_started,
        primary_started_epoch=primary_started_epoch,
        primary_started_local_iso=primary_started_local_iso,
        resolved_harness_session_id=resolved_harness_session_id,
    )


__all__ = [
    "LaunchContext",
    "ProcessOutcome",
    "active_primary_lock_path",
    "cleanup_orphaned_locks",
    "prepare_launch_context",
    "primary_launch_lock",
    "run_harness_process",
]
