"""Cross-platform process liveness via psutil."""

import psutil

_PID_REUSE_GUARD_SECS = 30.0


def is_process_alive(pid: int, created_after_epoch: float | None = None) -> bool:
    """Check if a PID is alive, with create_time guard for PID reuse."""
    if not psutil.pid_exists(pid):
        return False

    try:
        proc = psutil.Process(pid)
        # Process created after the tracked start time is PID reuse.
        if (
            created_after_epoch is not None
            and proc.create_time() > created_after_epoch + _PID_REUSE_GUARD_SECS
        ):
            return False
        return proc.is_running()
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
