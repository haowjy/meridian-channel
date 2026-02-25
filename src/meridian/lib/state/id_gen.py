"""Counter-based ID generation for workspaces and runs."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from meridian.lib.types import RunId, WorkspaceId

_WORKSPACE_COUNTER_KEY = "counter:workspace"
_GLOBAL_RUN_COUNTER_KEY = "counter:run:global"


@dataclass(frozen=True, slots=True)
class GeneratedRunId:
    """Run ID parts used for DB and filesystem layouts."""

    full_id: RunId
    local_id: RunId
    workspace_id: WorkspaceId | None


def _ensure_counter_key(conn: sqlite3.Connection, key: str) -> None:
    conn.execute(
        """
        INSERT INTO schema_info(key, value)
        VALUES(?, '0')
        ON CONFLICT(key) DO NOTHING
        """,
        (key,),
    )


def _next_counter(conn: sqlite3.Connection, key: str) -> int:
    _ensure_counter_key(conn, key)
    row = conn.execute(
        """
        UPDATE schema_info
        SET value = CAST(value AS INTEGER) + 1
        WHERE key = ?
        RETURNING value
        """,
        (key,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Counter key missing: {key}")
    return int(row[0])


def next_workspace_id(conn: sqlite3.Connection) -> WorkspaceId:
    """Return the next monotonic workspace ID (`w1`, `w2`, ...)."""

    return WorkspaceId(f"w{_next_counter(conn, _WORKSPACE_COUNTER_KEY)}")


def next_run_id(
    conn: sqlite3.Connection,
    workspace_id: WorkspaceId | None,
) -> GeneratedRunId:
    """Return the next run ID.

    Workspace-scoped IDs are generated as `w3/r1` with local part `r1`.
    Standalone run IDs are generated as `r1` where full and local ID match.
    """

    if workspace_id is None:
        local = RunId(f"r{_next_counter(conn, _GLOBAL_RUN_COUNTER_KEY)}")
        return GeneratedRunId(full_id=local, local_id=local, workspace_id=None)

    row = conn.execute(
        """
        UPDATE workspaces
        SET run_counter = run_counter + 1,
            last_activity_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        WHERE id = ?
        RETURNING run_counter
        """,
        (str(workspace_id),),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown workspace ID: {workspace_id}")

    local = RunId(f"r{int(row[0])}")
    return GeneratedRunId(
        full_id=RunId(f"{workspace_id}/{local}"),
        local_id=local,
        workspace_id=workspace_id,
    )
