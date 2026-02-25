"""SQLite connection management for Meridian state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.state.schema import apply_migrations

DEFAULT_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True, slots=True)
class StatePaths:
    """Resolved on-disk locations for Meridian state artifacts."""

    root_dir: Path
    index_dir: Path
    db_path: Path
    jsonl_path: Path
    lock_path: Path


def resolve_state_paths(repo_root: Path) -> StatePaths:
    """Resolve all state paths under `repo_root/.meridian`."""

    root_dir = repo_root / ".meridian"
    index_dir = root_dir / "index"
    return StatePaths(
        root_dir=root_dir,
        index_dir=index_dir,
        db_path=index_dir / "runs.db",
        jsonl_path=index_dir / "runs.jsonl",
        lock_path=index_dir / "runs.lock",
    )


def open_connection(
    db_path: Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """Open a configured SQLite connection and run embedded migrations."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    apply_migrations(conn)
    return conn


def open_connection_for_repo(
    repo_root: Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> tuple[sqlite3.Connection, StatePaths]:
    """Open a configured SQLite connection for a repository root."""

    paths = resolve_state_paths(repo_root)
    return open_connection(paths.db_path, busy_timeout_ms=busy_timeout_ms), paths


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
