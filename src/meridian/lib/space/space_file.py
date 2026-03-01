"""File-backed space metadata CRUD for `.meridian/.spaces/<space-id>/space.json`."""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from meridian.lib.state.id_gen import next_space_id
from meridian.lib.state.paths import SpacePaths, ensure_gitignore, resolve_all_spaces_dir, resolve_space_dir
from meridian.lib.types import SpaceId

type SpaceStatus = Literal["active", "closed"]

_SPACE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SpaceRecord:
    """Serialized form of one space record."""

    schema_version: int
    id: str
    name: str | None
    status: SpaceStatus
    created_at: str
    finished_at: str | None


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@contextmanager
def _lock_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_space_json(path: Path, record: SpaceRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(record), handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


def _read_space_json(path: Path) -> SpaceRecord | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    status = payload.get("status")
    if status not in {"active", "closed"}:
        return None

    return SpaceRecord(
        schema_version=int(payload.get("schema_version", _SPACE_SCHEMA_VERSION)),
        id=str(payload.get("id")),
        name=payload.get("name") if payload.get("name") is None else str(payload.get("name")),
        status=status,
        created_at=str(payload.get("created_at")),
        finished_at=(
            payload.get("finished_at")
            if payload.get("finished_at") is None
            else str(payload.get("finished_at"))
        ),
    )


def create_space(repo_root: Path, name: str | None = None) -> SpaceRecord:
    """Create one new active space and write `space.json`."""

    spaces_dir = resolve_all_spaces_dir(repo_root)
    spaces_dir.mkdir(parents=True, exist_ok=True)
    with _lock_file(spaces_dir / ".lock"):
        space_id = next_space_id(repo_root)
        space_dir = resolve_space_dir(repo_root, space_id)
        paths = SpacePaths.from_space_dir(space_dir)
        paths.fs_dir.mkdir(parents=True, exist_ok=False)

        record = SpaceRecord(
            schema_version=_SPACE_SCHEMA_VERSION,
            id=str(space_id),
            name=name,
            status="active",
            created_at=_utc_now_iso(),
            finished_at=None,
        )
        _write_space_json(paths.space_json, record)

    ensure_gitignore(repo_root)
    return record


def get_space(repo_root: Path, space_id: SpaceId | str) -> SpaceRecord | None:
    """Load one `space.json` record."""

    path = SpacePaths.from_space_dir(resolve_space_dir(repo_root, space_id)).space_json
    return _read_space_json(path)


def list_spaces(repo_root: Path) -> list[SpaceRecord]:
    """Load all valid spaces from `.meridian/.spaces/*/space.json`."""

    spaces_dir = resolve_all_spaces_dir(repo_root)
    if not spaces_dir.exists():
        return []

    records: list[SpaceRecord] = []
    for child in sorted(spaces_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        record = _read_space_json(SpacePaths.from_space_dir(child).space_json)
        if record is not None:
            records.append(record)
    return records


def update_space_status(
    repo_root: Path,
    space_id: SpaceId | str,
    new_status: SpaceStatus,
) -> SpaceRecord:
    """Update `space.json.status` with locked read-modify-write semantics."""

    if new_status not in {"active", "closed"}:
        raise ValueError("Space status must be 'active' or 'closed'.")

    paths = SpacePaths.from_space_dir(resolve_space_dir(repo_root, space_id))
    with _lock_file(paths.space_lock):
        current = _read_space_json(paths.space_json)
        if current is None:
            raise ValueError(f"Space '{space_id}' not found or invalid.")

        finished_at = current.finished_at
        if new_status == "closed":
            finished_at = finished_at or _utc_now_iso()
        else:
            finished_at = None

        updated = SpaceRecord(
            schema_version=current.schema_version,
            id=current.id,
            name=current.name,
            status=new_status,
            created_at=current.created_at,
            finished_at=finished_at,
        )
        _write_space_json(paths.space_json, updated)
        return updated
