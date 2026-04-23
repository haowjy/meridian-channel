"""Shared managed-primary runtime helpers."""

from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.state.liveness import is_process_alive
from meridian.lib.state.primary_meta import PrimaryMetadata, read_primary_metadata
from meridian.lib.state.spawn_store import SpawnRecord


@dataclass(frozen=True)
class ManagedPrimarySnapshot:
    """Snapshot of managed primary runtime state for reconciliation."""

    metadata: PrimaryMetadata
    launcher_pid_alive: bool
    started_epoch: float | None


def read_managed_primary_snapshot(
    runtime_root: Path,
    record: SpawnRecord,
    *,
    started_epoch: float | None = None,
) -> ManagedPrimarySnapshot | None:
    """Read managed primary snapshot for reconciliation decisions."""

    metadata = read_primary_metadata(runtime_root, record.id)
    if metadata is None or not metadata.managed_backend:
        return None

    launcher_pid_alive = False
    if metadata.launcher_pid is not None:
        launcher_pid_alive = is_process_alive(
            metadata.launcher_pid,
            created_after_epoch=started_epoch,
        )

    return ManagedPrimarySnapshot(
        metadata=metadata,
        launcher_pid_alive=launcher_pid_alive,
        started_epoch=started_epoch,
    )


def _terminate_pid(pid: int) -> bool:
    """Send SIGTERM to a single PID."""

    if pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return False
    return True


def terminate_managed_primary_processes(
    primary_metadata: PrimaryMetadata | None,
    *,
    started_epoch: float | None = None,
    include_launcher: bool,
    include_runtime_children: bool = True,
) -> tuple[int, ...]:
    """Best-effort SIGTERM for tracked managed-primary processes."""

    if primary_metadata is None or not primary_metadata.managed_backend:
        return ()

    if include_launcher and include_runtime_children:
        candidates = (
            primary_metadata.launcher_pid,
            primary_metadata.backend_pid,
            primary_metadata.tui_pid,
        )
    elif include_launcher:
        candidates = (primary_metadata.launcher_pid,)
    else:
        candidates = (
            primary_metadata.backend_pid,
            primary_metadata.tui_pid,
        )

    signaled: list[int] = []
    seen: set[int] = set()
    for candidate in candidates:
        if candidate is None or candidate in seen:
            continue
        seen.add(candidate)
        if not is_process_alive(candidate, created_after_epoch=started_epoch):
            continue
        if _terminate_pid(candidate):
            signaled.append(candidate)
    return tuple(signaled)


__all__ = [
    "ManagedPrimarySnapshot",
    "read_managed_primary_snapshot",
    "terminate_managed_primary_processes",
]
