"""Process launch package with compatibility wrappers."""

from __future__ import annotations

import signal
import struct
from pathlib import Path
from typing import Any, cast

from meridian.lib.platform import fcntl, termios
from meridian.lib.state.session_store import (
    get_session_active_work_id,
    start_session,
    stop_session,
    update_session_harness_id,
    update_session_work_id,
)

from .ports import ChildStartedHook, LaunchedProcess, ProcessLauncher
from .pty_launcher import (
    _invoke_previous_sigwinch_handler,
    _sync_pty_winsize as _sync_pty_winsize_impl,
    can_use_pty,
)
from .runner import (
    ProcessOutcome,
    run_harness_process as _run_harness_process_impl,
    run_primary_process_with_capture as _run_primary_process_with_capture_impl,
)


def _sync_pty_winsize(*, source_fd: int, target_fd: int) -> None:
    _sync_pty_winsize_impl(source_fd=source_fd, target_fd=target_fd)


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


def _run_primary_process_with_capture(
    *,
    command: tuple[str, ...],
    cwd: Path,
    env: dict[str, str],
    output_log_path: Path | None,
    on_child_started: ChildStartedHook | None = None,
) -> tuple[int, int | None]:
    return _run_primary_process_with_capture_impl(
        command,
        cwd,
        env,
        output_log_path,
        on_child_started,
    )


def run_harness_process(launch_context: Any, harness_registry: Any) -> Any:
    # Preserve monkeypatch seams currently exercised in tests.
    return _run_harness_process_impl(
        launch_context,
        harness_registry,
        run_primary_process_with_capture_fn=lambda command, cwd, env, output_log_path, on_child_started=None: _run_primary_process_with_capture(
            command=command,
            cwd=cwd,
            env=env,
            output_log_path=output_log_path,
            on_child_started=on_child_started,
        ),
        start_session_fn=start_session,
        stop_session_fn=stop_session,
        update_session_harness_id_fn=update_session_harness_id,
        update_session_work_id_fn=update_session_work_id,
        get_session_active_work_id_fn=get_session_active_work_id,
    )


__all__ = [
    "ChildStartedHook",
    "LaunchedProcess",
    "ProcessLauncher",
    "ProcessOutcome",
    "can_use_pty",
    "run_harness_process",
]
