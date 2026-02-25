"""Workspace CRUD helpers with lifecycle transition guards."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import Workspace, WorkspaceCreateParams, WorkspaceState
from meridian.lib.types import WorkspaceId

_ALLOWED_TRANSITIONS: Mapping[WorkspaceState, frozenset[WorkspaceState]] = {
    "active": frozenset({"paused", "completed", "abandoned"}),
    "paused": frozenset({"active", "completed", "abandoned"}),
    "completed": frozenset(),
    "abandoned": frozenset(),
}


def create_workspace(state: StateDB, *, name: str | None = None) -> Workspace:
    """Create one active workspace row."""

    return state.create_workspace(WorkspaceCreateParams(name=name))


def get_workspace_or_raise(state: StateDB, workspace_id: WorkspaceId) -> Workspace:
    """Fetch a workspace and raise when it does not exist."""

    workspace = state.get_workspace(workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace '{workspace_id}' not found")
    return workspace


def resolve_workspace_for_resume(state: StateDB, workspace: str | None) -> WorkspaceId:
    """Resolve resume target from explicit value or most-recent active workspace."""

    if workspace is not None and workspace.strip():
        return WorkspaceId(workspace.strip())

    conn = sqlite3.connect(state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id
            FROM workspaces
            WHERE status = 'active'
            ORDER BY last_activity_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is not None:
            return WorkspaceId(str(row["id"]))

        fallback = conn.execute(
            "SELECT id FROM workspaces ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    if fallback is None:
        raise ValueError("No workspace available to resume.")
    return WorkspaceId(str(fallback["id"]))


def can_transition(current: WorkspaceState, new_state: WorkspaceState) -> bool:
    """Return whether one workspace lifecycle transition is valid."""

    if current == new_state:
        return True
    return new_state in _ALLOWED_TRANSITIONS[current]


def transition_workspace(
    state: StateDB,
    workspace_id: WorkspaceId,
    new_state: WorkspaceState,
) -> Workspace:
    """Apply a validated workspace lifecycle transition."""

    workspace = get_workspace_or_raise(state, workspace_id)
    current = workspace.state
    if not can_transition(current, new_state):
        raise ValueError(
            "Invalid workspace transition "
            f"'{workspace_id}': {current} -> {new_state}."
        )

    if current != new_state:
        state.transition_workspace(workspace_id, new_state)

    return get_workspace_or_raise(state, workspace_id)
