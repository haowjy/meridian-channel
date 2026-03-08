"""File-backed sync lock models and helpers."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field


class SyncLockEntry(BaseModel):
    """One provenance record for a synced skill or agent."""

    model_config = ConfigDict(frozen=True)

    source_name: str
    source_type: Literal["repo", "path"]
    source_value: str
    source_item_name: str
    requested_ref: str | None
    locked_commit: str | None
    item_kind: Literal["skill", "agent"]
    dest_path: str
    tree_hash: str
    synced_at: str


class SyncLockFile(BaseModel):
    """Serialized `.meridian/sync.lock` content."""

    version: int = 1
    items: dict[str, SyncLockEntry] = Field(default_factory=dict)


def _tmp_path(lock_path: Path) -> Path:
    return lock_path.with_name(f"{lock_path.name}.tmp")


def _flock_path(lock_path: Path) -> Path:
    return lock_path.with_name(f"{lock_path.name}.flock")


def read_lock_file(lock_path: Path) -> SyncLockFile:
    """Read and validate `.meridian/sync.lock`."""

    try:
        raw = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SyncLockFile()

    payload = json.loads(raw)
    return SyncLockFile.model_validate(cast("dict[str, object]", payload))


def write_lock_file(lock_path: Path, lock: SyncLockFile) -> None:
    """Write `.meridian/sync.lock` atomically."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _tmp_path(lock_path)

    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(lock.model_dump(mode="json"), handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, lock_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


@contextmanager
def lock_file_guard(lock_path: Path) -> Iterator[None]:
    """Acquire an exclusive advisory lock for the sync lock file."""

    flock_path = _flock_path(lock_path)
    flock_path.parent.mkdir(parents=True, exist_ok=True)
    with flock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
