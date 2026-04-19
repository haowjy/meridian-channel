"""Subprocess-backed process launching."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

from .ports import ChildStartedHook, LaunchedProcess, ProcessLauncher


class SubprocessProcessLauncher(ProcessLauncher):
    """Portable subprocess launcher used when PTY capture is unavailable."""

    def launch(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
        on_child_started: ChildStartedHook | None = None,
    ) -> LaunchedProcess:
        _ = output_log_path
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
            return LaunchedProcess(exit_code=process.wait(), pid=process.pid)
        except KeyboardInterrupt:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                return LaunchedProcess(exit_code=process.wait(), pid=process.pid)
            return LaunchedProcess(exit_code=130, pid=process.pid)


__all__ = ["SubprocessProcessLauncher"]
