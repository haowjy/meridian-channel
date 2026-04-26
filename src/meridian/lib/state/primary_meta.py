"""Canonical schema and I/O helpers for managed primary metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from meridian.lib.launch.constants import PRIMARY_META_FILENAME
from meridian.lib.state.atomic import atomic_write_text

ActivityState = Literal["starting", "idle", "turn_active", "finalizing"]


@dataclass(frozen=True)
class PrimaryMetadata:
    """Canonical schema for primary_meta.json."""

    managed_backend: bool = True
    launcher_pid: int | None = None
    backend_pid: int | None = None
    tui_pid: int | None = None
    backend_port: int | None = None
    activity: ActivityState | None = None
    harness_session_id: str | None = None


@dataclass(frozen=True)
class PrimarySurfaceMetadata:
    """Projection for spawn list/show surfaces."""

    managed_backend: bool
    activity: str | None
    backend_pid: int | None
    tui_pid: int | None
    backend_port: int | None
    harness_session_id: str | None


def primary_meta_path(
    *,
    runtime_root: Path | None = None,
    spawn_dir: Path | None = None,
    spawn_id: str | None = None,
) -> Path:
    """Resolve path to primary_meta.json.

    Exactly one of spawn_dir or (runtime_root, spawn_id) must be provided.
    """

    has_spawn_dir = spawn_dir is not None
    has_runtime_pair = runtime_root is not None or spawn_id is not None

    if has_spawn_dir and has_runtime_pair:
        raise ValueError("Provide either spawn_dir or runtime_root+spawn_id, not both")
    if has_spawn_dir:
        return spawn_dir / PRIMARY_META_FILENAME
    if runtime_root is None or spawn_id is None:
        raise ValueError("runtime_root and spawn_id are required when spawn_dir is not provided")
    return runtime_root / "spawns" / spawn_id / PRIMARY_META_FILENAME


def _coerce_positive_int(value: object) -> int | None:
    if not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def _coerce_activity_state(value: object) -> ActivityState | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized not in {"starting", "idle", "turn_active", "finalizing"}:
        return None
    return cast("ActivityState", normalized)


def _coerce_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def read_primary_metadata(runtime_root: Path, spawn_id: str) -> PrimaryMetadata | None:
    """Tolerant read with crash-only semantics. Returns None for missing/corrupt file."""

    metadata_path = primary_meta_path(runtime_root=runtime_root, spawn_id=spawn_id)
    if not metadata_path.is_file():
        return None
    try:
        payload_obj = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload_obj, dict):
        return None

    payload = cast("dict[str, object]", payload_obj)
    if payload.get("managed_backend") is not True:
        return None

    return PrimaryMetadata(
        managed_backend=True,
        launcher_pid=_coerce_positive_int(payload.get("launcher_pid")),
        backend_pid=_coerce_positive_int(payload.get("backend_pid")),
        tui_pid=_coerce_positive_int(payload.get("tui_pid")),
        backend_port=_coerce_positive_int(payload.get("backend_port")),
        activity=_coerce_activity_state(payload.get("activity")),
        harness_session_id=_coerce_optional_text(payload.get("harness_session_id")),
    )


def write_primary_metadata(spawn_dir: Path, metadata: PrimaryMetadata) -> None:
    """Atomic write via tmp+rename."""

    payload = {
        "managed_backend": metadata.managed_backend,
        "launcher_pid": metadata.launcher_pid,
        "backend_pid": metadata.backend_pid,
        "tui_pid": metadata.tui_pid,
        "backend_port": metadata.backend_port,
        "activity": metadata.activity,
        "harness_session_id": metadata.harness_session_id,
    }
    atomic_write_text(
        primary_meta_path(spawn_dir=spawn_dir),
        json.dumps(payload, separators=(",", ":")) + "\n",
    )


def read_primary_surface_metadata(runtime_root: Path, spawn_id: str) -> PrimarySurfaceMetadata:
    """Read projection for CLI surfaces. Returns defaults if file missing."""

    metadata = read_primary_metadata(runtime_root, spawn_id)
    if metadata is None:
        return PrimarySurfaceMetadata(
            managed_backend=False,
            activity=None,
            backend_pid=None,
            tui_pid=None,
            backend_port=None,
            harness_session_id=None,
        )
    return PrimarySurfaceMetadata(
        managed_backend=metadata.managed_backend,
        activity=metadata.activity,
        backend_pid=metadata.backend_pid,
        tui_pid=metadata.tui_pid,
        backend_port=metadata.backend_port,
        harness_session_id=metadata.harness_session_id,
    )


def read_primary_harness_session_id(runtime_root: Path, spawn_id: str) -> str | None:
    """Read harness_session_id only. Used by session_log resolution."""

    metadata = read_primary_metadata(runtime_root, spawn_id)
    if metadata is None:
        return None
    return metadata.harness_session_id


def is_managed_primary(runtime_root: Path, spawn_id: str) -> bool:
    """Check if spawn is a managed primary."""

    metadata = read_primary_metadata(runtime_root, spawn_id)
    return bool(metadata is not None and metadata.managed_backend)


__all__ = [
    "ActivityState",
    "PrimaryMetadata",
    "PrimarySurfaceMetadata",
    "is_managed_primary",
    "primary_meta_path",
    "read_primary_harness_session_id",
    "read_primary_metadata",
    "read_primary_surface_metadata",
    "write_primary_metadata",
]
