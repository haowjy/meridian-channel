"""SQLite schema definitions and embedded forward-only migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

SchemaMigration = Callable[[sqlite3.Connection], None]
SCHEMA_VERSION_KEY = "version"
LATEST_SCHEMA_VERSION = 2

REQUIRED_TABLES: frozenset[str] = frozenset(
    {
        "runs",
        "workspaces",
        "pinned_files",
        "workflow_events",
        "spans",
        "run_edges",
        "artifacts",
        "schema_info",
    }
)


def _migration_001_init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT NOT NULL,
            description TEXT,
            plan_file TEXT,
            labels TEXT NOT NULL DEFAULT '{}',
            supervisor_model TEXT,
            supervisor_harness TEXT,
            supervisor_harness_session_id TEXT,
            started_at TEXT NOT NULL,
            last_activity_at TEXT NOT NULL,
            finished_at TEXT,
            total_runs INTEGER NOT NULL DEFAULT 0,
            total_cost_usd REAL NOT NULL DEFAULT 0.0,
            total_input_tokens INTEGER NOT NULL DEFAULT 0,
            total_output_tokens INTEGER NOT NULL DEFAULT 0,
            summary_path TEXT,
            run_counter INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT REFERENCES workspaces(id),
            local_id TEXT NOT NULL,
            run_type TEXT NOT NULL DEFAULT 'run_agent',
            name TEXT,
            prompt TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL,
            agent TEXT,
            skills TEXT NOT NULL DEFAULT '[]',
            labels TEXT NOT NULL DEFAULT '{}',
            harness TEXT NOT NULL,
            harness_version TEXT,
            status TEXT NOT NULL,
            exit_code INTEGER,
            failure_reason TEXT,
            dedup_key TEXT,
            starred INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_secs REAL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_cost_usd REAL,
            quality_score REAL,
            task_type TEXT,
            git_branch TEXT,
            git_head_before TEXT,
            git_head_after TEXT,
            continues_run TEXT,
            retries_run TEXT,
            harness_session_id TEXT,
            cwd TEXT,
            log_dir TEXT NOT NULL,
            output_log TEXT,
            report_path TEXT,
            error_message TEXT,
            files_touched_count INTEGER
        );

        CREATE TABLE IF NOT EXISTS pinned_files (
            workspace_id TEXT NOT NULL REFERENCES workspaces(id),
            file_path TEXT NOT NULL,
            pinned_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            pinned_by TEXT,
            PRIMARY KEY (workspace_id, file_path)
        );

        CREATE TABLE IF NOT EXISTS workflow_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id),
            event_type TEXT NOT NULL,
            run_id TEXT,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_id TEXT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL DEFAULT 'ok',
            attributes TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS run_edges (
            source_run_id TEXT NOT NULL REFERENCES runs(id),
            target_run_id TEXT NOT NULL REFERENCES runs(id),
            edge_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            PRIMARY KEY (source_run_id, target_run_id, edge_type)
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            run_id TEXT NOT NULL REFERENCES runs(id),
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            size INTEGER,
            PRIMARY KEY (run_id, name)
        );

        CREATE TABLE IF NOT EXISTS schema_info (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(status);
        CREATE INDEX IF NOT EXISTS idx_workspaces_started ON workspaces(started_at);
        CREATE INDEX IF NOT EXISTS idx_runs_workspace ON runs(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
        CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
        CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);
        CREATE INDEX IF NOT EXISTS idx_runs_dedup ON runs(dedup_key);
        CREATE INDEX IF NOT EXISTS idx_runs_type ON runs(run_type);
        CREATE INDEX IF NOT EXISTS idx_pinned_workspace ON pinned_files(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_events_workspace ON workflow_events(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
        """
    )


def _migration_002_add_files_touched_count(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN files_touched_count INTEGER")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


MIGRATIONS: dict[int, SchemaMigration] = {
    1: _migration_001_init,
    2: _migration_002_add_files_touched_count,
}


def _ensure_schema_info_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_info (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version from schema_info."""

    _ensure_schema_info_table(conn)
    row = conn.execute(
        "SELECT value FROM schema_info WHERE key = ?",
        (SCHEMA_VERSION_KEY,),
    ).fetchone()
    if row is None:
        return 0
    return int(row[0])


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        """
        INSERT INTO schema_info(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (SCHEMA_VERSION_KEY, str(version)),
    )


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply embedded migrations in ascending order (forward-only)."""

    _ensure_schema_info_table(conn)
    current_version = get_schema_version(conn)
    if current_version > LATEST_SCHEMA_VERSION:
        msg = (
            "Schema version is newer than this binary supports: "
            f"{current_version} > {LATEST_SCHEMA_VERSION}"
        )
        raise RuntimeError(msg)

    for version in sorted(MIGRATIONS):
        if version <= current_version:
            continue
        with conn:
            MIGRATIONS[version](conn)
            set_schema_version(conn, version)
        current_version = version

    return current_version


def list_tables(conn: sqlite3.Connection) -> set[str]:
    """Return non-internal table names."""

    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}
