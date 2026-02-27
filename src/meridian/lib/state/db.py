"""SQLite connection management for Meridian state."""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from meridian.lib.state.schema import apply_migrations

if TYPE_CHECKING:
    from meridian.lib.types import RunId, WorkspaceId

DEFAULT_BUSY_TIMEOUT_MS = 5000
DEFAULT_LOCK_RETRIES = 3
DEFAULT_LOCK_BACKOFF_SECS = 0.05
_LOCK_CONTENTION_MARKERS: tuple[str, ...] = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
    "locked",
)
_CORRUPTION_MARKERS: tuple[str, ...] = (
    "database disk image is malformed",
    "disk image is malformed",
    "malformed",
    "database is corrupt",
    "file is not a database",
)


@dataclass(frozen=True, slots=True)
class StatePaths:
    """Resolved on-disk locations for Meridian state artifacts."""

    root_dir: Path
    index_dir: Path
    db_path: Path
    jsonl_path: Path
    lock_path: Path
    artifacts_dir: Path
    runs_dir: Path
    workspaces_dir: Path
    active_workspaces_dir: Path
    config_path: Path
    models_path: Path


def _resolve_state_root(repo_root: Path) -> Path:
    """Resolve state root from env override or default `.meridian` location."""

    override = os.getenv("MERIDIAN_STATE_ROOT", "").strip()
    if not override:
        return repo_root / ".meridian"

    candidate = Path(override).expanduser()
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def resolve_state_paths(repo_root: Path) -> StatePaths:
    """Resolve all meridian state paths from one shared root."""

    root_dir = _resolve_state_root(repo_root)
    index_dir = root_dir / "index"
    return StatePaths(
        root_dir=root_dir,
        index_dir=index_dir,
        db_path=index_dir / "runs.db",
        jsonl_path=index_dir / "runs.jsonl",
        lock_path=index_dir / "runs.lock",
        artifacts_dir=root_dir / "artifacts",
        runs_dir=root_dir / "runs",
        workspaces_dir=root_dir / "workspaces",
        active_workspaces_dir=root_dir / "active-workspaces",
        config_path=root_dir / "config.toml",
        models_path=root_dir / "models.toml",
    )


def run_log_subpath(run_id: RunId, workspace_id: WorkspaceId | None) -> Path:
    """Return run log subpath beneath the state root."""

    if workspace_id is None:
        return Path("runs") / str(run_id)

    local_id = str(run_id).split("/")[-1]
    return Path("workspaces") / str(workspace_id) / "runs" / local_id


def resolve_run_log_dir(repo_root: Path, run_id: RunId, workspace_id: WorkspaceId | None) -> Path:
    """Resolve absolute run log directory for run/workspace IDs."""

    return resolve_state_paths(repo_root).root_dir / run_log_subpath(run_id, workspace_id)


def open_connection(
    db_path: Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    lock_retries: int = DEFAULT_LOCK_RETRIES,
    lock_backoff_secs: float = DEFAULT_LOCK_BACKOFF_SECS,
) -> sqlite3.Connection:
    """Open a configured SQLite connection and run embedded migrations."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    attempts = 0
    while True:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
            apply_migrations(conn)
            return conn
        except sqlite3.DatabaseError as exc:
            if conn is not None:
                conn.close()
            normalized = str(exc).lower()
            if any(marker in normalized for marker in _LOCK_CONTENTION_MARKERS):
                if attempts < max(lock_retries, 0):
                    delay = max(lock_backoff_secs, 0.0) * (2**attempts)
                    attempts += 1
                    if delay > 0:
                        time.sleep(delay)
                    continue
            if any(marker in normalized for marker in _CORRUPTION_MARKERS):
                message = (
                    f"Meridian state database appears corrupt: '{db_path.as_posix()}'. "
                    "Run `meridian diag doctor` (or remove the DB to rebuild) and retry."
                )
                raise sqlite3.OperationalError(message) from exc
            raise


def open_connection_for_repo(
    repo_root: Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    lock_retries: int = DEFAULT_LOCK_RETRIES,
    lock_backoff_secs: float = DEFAULT_LOCK_BACKOFF_SECS,
) -> tuple[sqlite3.Connection, StatePaths]:
    """Open a configured SQLite connection for a repository root."""

    paths = resolve_state_paths(repo_root)
    return (
        open_connection(
            paths.db_path,
            busy_timeout_ms=busy_timeout_ms,
            lock_retries=lock_retries,
            lock_backoff_secs=lock_backoff_secs,
        ),
        paths,
    )


def get_journal_mode(conn: sqlite3.Connection) -> str:
    """Read the effective journal mode for assertions and diagnostics."""

    row = conn.execute("PRAGMA journal_mode").fetchone()
    if row is None:
        return ""
    return str(row[0]).lower()


def get_busy_timeout(conn: sqlite3.Connection) -> int:
    """Read the effective busy timeout in milliseconds."""

    row = conn.execute("PRAGMA busy_timeout").fetchone()
    if row is None:
        return 0
    return int(row[0])
