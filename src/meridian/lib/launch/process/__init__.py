"""Process launch package with backward-compatible exports."""

from __future__ import annotations

import importlib.util
import signal
import struct
import sys
from pathlib import Path
from typing import Any, cast

from meridian.lib.platform import fcntl, termios

from .ports import LaunchedProcess, ProcessLauncher

_LEGACY_MODULE_NAME = "meridian.lib.launch._process_legacy"


def _load_legacy_module() -> Any:
    existing = sys.modules.get(_LEGACY_MODULE_NAME)
    if existing is not None:
        return existing

    legacy_path = Path(__file__).resolve().parent.with_suffix(".py")
    spec = importlib.util.spec_from_file_location(_LEGACY_MODULE_NAME, legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy process module from {legacy_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_LEGACY_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy_module()

ProcessOutcome = _legacy.ProcessOutcome

start_session = _legacy.start_session
stop_session = _legacy.stop_session
update_session_harness_id = _legacy.update_session_harness_id
update_session_work_id = _legacy.update_session_work_id
get_session_active_work_id = _legacy.get_session_active_work_id

_DEFAULT_SYNC_PTY_WINSIZE = _legacy._sync_pty_winsize
_DEFAULT_RUN_PRIMARY_PROCESS_WITH_CAPTURE = _legacy._run_primary_process_with_capture


def _sync_pty_winsize(*, source_fd: int, target_fd: int) -> None:
    _DEFAULT_SYNC_PTY_WINSIZE(source_fd=source_fd, target_fd=target_fd)


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
    _sync_pty_winsize(source_fd=source_fd, target_fd=target_fd)
    previous = cast("signal.Handlers", signal.getsignal(signal.SIGWINCH))

    def _handle_resize(signum: int, frame: Any) -> None:
        _sync_pty_winsize(source_fd=source_fd, target_fd=target_fd)
        _invoke_previous_sigwinch_handler(previous, signum=signum, frame=frame)

    signal.signal(signal.SIGWINCH, _handle_resize)

    def _restore() -> None:
        signal.signal(signal.SIGWINCH, previous)

    return _restore


def _run_primary_process_with_capture(
    *,
    command: tuple[str, ...],
    cwd: Path,
    env: dict[str, str],
    output_log_path: Path | None,
    on_child_started: Any | None = None,
) -> tuple[int, int | None]:
    return _DEFAULT_RUN_PRIMARY_PROCESS_WITH_CAPTURE(
        command=command,
        cwd=cwd,
        env=env,
        output_log_path=output_log_path,
        on_child_started=on_child_started,
    )


def run_harness_process(launch_context: Any, harness_registry: Any) -> Any:
    # Keep monkeypatch seams stable for current tests and callers.
    _legacy._sync_pty_winsize = _sync_pty_winsize
    _legacy._install_winsize_forwarding = _install_winsize_forwarding
    _legacy._run_primary_process_with_capture = _run_primary_process_with_capture
    _legacy.start_session = start_session
    _legacy.stop_session = stop_session
    _legacy.update_session_harness_id = update_session_harness_id
    _legacy.update_session_work_id = update_session_work_id
    _legacy.get_session_active_work_id = get_session_active_work_id
    return _legacy.run_harness_process(launch_context, harness_registry)


__all__ = [
    "LaunchedProcess",
    "ProcessLauncher",
    "ProcessOutcome",
    "run_harness_process",
]
