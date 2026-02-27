"""Process-group helpers for subprocess lifecycle management."""

from __future__ import annotations

import asyncio
import os
import signal


def signal_process_group(
    process: asyncio.subprocess.Process,
    signum: signal.Signals,
) -> None:
    """Send one signal to the subprocess process group.

    The child may exit between returncode checks and signal delivery, so
    ProcessLookupError is treated as an expected race.
    """

    if process.returncode is not None:
        return

    pid = process.pid
    if pid is None:
        return

    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signum)
    except ProcessLookupError:
        return
