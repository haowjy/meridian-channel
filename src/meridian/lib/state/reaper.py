"""Spawn reconciliation: detect and clean up orphaned/stuck spawns.

This module is the single place where stuck-spawn policy lives. It runs on
every user-facing read path (list, show, wait, dashboard) so that stale or
orphaned spawns are repaired transparently — no separate "gc" command needed.
"""

from __future__ import annotations

import os
import signal as _signal
import time
from pathlib import Path

import structlog

from meridian.lib.state.spawn_store import SpawnRecord, finalize_spawn_if_running
from meridian.lib.core.types import SpawnId

logger = structlog.get_logger(__name__)

_STALE_THRESHOLD_SECS = 300  # 5 minutes of no output = stale


# ---------------------------------------------------------------------------
# PID helpers
# ---------------------------------------------------------------------------


def _read_pid_file(spawn_dir: Path, filename: str) -> int | None:
    """Read and parse a .pid file. Return None if missing/invalid."""
    pid_path = spawn_dir / filename
    if not pid_path.is_file():
        return None
    try:
        value = int(pid_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    return value if value > 0 else None


def _get_boot_time() -> float:
    """Read system boot time from /proc/stat (Linux only)."""
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("btime "):
                    return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def _pid_is_alive(pid: int, pid_file: Path) -> bool:
    """Check if a PID is alive, with /proc start-time guard for PID reuse."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Exists but we can't signal it

    # Guard against PID reuse on Linux via /proc start time
    try:
        stat_path = Path(f"/proc/{pid}/stat")
        if stat_path.exists():
            # Field 22 (0-indexed: 21) is starttime in clock ticks
            fields = stat_path.read_text().split()
            start_ticks = int(fields[21])
            boot_time = _get_boot_time()
            clock_hz = os.sysconf("SC_CLK_TCK")
            proc_start = boot_time + start_ticks / clock_hz
            pid_file_mtime = pid_file.stat().st_mtime
            # If process started after PID file was written, it's a reused PID
            if proc_start > pid_file_mtime + 2:  # 2s tolerance
                return False
    except (OSError, ValueError, IndexError):
        pass  # Non-Linux or can't check — assume alive

    return True


def _spawn_is_stale(spawn_dir: Path, pid_file: Path) -> bool:
    """Check if a spawn has stopped producing output for >5 minutes."""
    now = time.time()
    # Check output files first
    for name in ("output.jsonl", "stderr.log"):
        path = spawn_dir / name
        try:
            if now - path.stat().st_mtime < _STALE_THRESHOLD_SECS:
                return False  # Recent activity
        except OSError:
            continue
    # If no output files exist, check pid file age as spawn start proxy
    try:
        if now - pid_file.stat().st_mtime < _STALE_THRESHOLD_SECS:
            return False  # Spawn started recently
    except OSError:
        pass
    return True


def _kill_pid_nonblocking(pid: int) -> None:
    """Send SIGTERM to a process group. Non-blocking, best-effort.

    Used on the read path so that stuck spawns are signalled to exit without
    blocking the caller.  The spawn is finalized immediately after this call,
    so even if the process lingers briefly it won't be "running" in state.
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return

    try:
        os.killpg(pgid, _signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


# ---------------------------------------------------------------------------
# Reconciliation — runs on every user-facing read
# ---------------------------------------------------------------------------


def _finalize_and_log(
    state_root: Path, record: SpawnRecord, error: str,
) -> SpawnRecord:
    """Finalize a running spawn as failed and return the updated record."""
    finalized = finalize_spawn_if_running(
        state_root,
        SpawnId(record.id),
        status="failed",
        exit_code=1,
        error=error,
    )
    if finalized:
        logger.info("Reconciled stuck spawn.", spawn_id=record.id, reason=error)
        return record.model_copy(update={"status": "failed", "exit_code": 1, "error": error})
    return record


def reconcile_running_spawn(state_root: Path, record: SpawnRecord) -> SpawnRecord:
    """Reconcile a single running spawn: detect stuck/orphaned state, kill if
    needed, and finalize.

    Three cases are handled:
      1. All known PIDs are dead → finalize as orphan (no kill needed).
      2. Alive + report.md exists → harness finished but wrapper hung.
         Send SIGTERM and finalize.
      3. Alive + stale (no output for 5 min) → process is stuck.
         Send SIGTERM and finalize.
    """
    if record.status != "running":
        return record

    spawn_dir = state_root / "spawns" / record.id
    bg_pid_file = spawn_dir / "background.pid"
    harness_pid_file = spawn_dir / "harness.pid"

    bg_pid = _read_pid_file(spawn_dir, "background.pid")
    harness_pid = _read_pid_file(spawn_dir, "harness.pid")

    if bg_pid is None and harness_pid is None:
        return record  # No PID files — can't determine state

    if bg_pid is None:
        # No background.pid — likely a foreground spawn managed by the runner.
        # We can't safely reconcile using harness.pid alone.
        return record

    # Check process liveness
    bg_alive = _pid_is_alive(bg_pid, bg_pid_file)
    harness_alive = harness_pid is not None and _pid_is_alive(harness_pid, harness_pid_file)

    # Case 1: all processes dead — orphan
    if not bg_alive and not harness_alive:
        return _finalize_and_log(state_root, record, "orphan_run")

    # Case 2: alive + report exists — harness completed, wrapper hung
    report_file = spawn_dir / "report.md"
    if report_file.exists():
        if harness_pid is not None and harness_alive:
            _kill_pid_nonblocking(harness_pid)
        if bg_alive:
            _kill_pid_nonblocking(bg_pid)
        return _finalize_and_log(state_root, record, "harness_completed")

    # Case 3: alive + stale — no output for too long
    if _spawn_is_stale(spawn_dir, bg_pid_file):
        if harness_pid is not None and harness_alive:
            _kill_pid_nonblocking(harness_pid)
        if bg_alive:
            _kill_pid_nonblocking(bg_pid)
        return _finalize_and_log(state_root, record, "stale")

    return record  # Spawn looks healthy — still producing output


def reconcile_spawns(state_root: Path, spawns: list[SpawnRecord]) -> list[SpawnRecord]:
    """Batch reconciliation. Only touches spawns with status=='running'."""
    return [
        reconcile_running_spawn(state_root, spawn) if spawn.status == "running" else spawn
        for spawn in spawns
    ]
