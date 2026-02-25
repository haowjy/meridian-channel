"""Operation runtime helpers for state/store resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.adapters.sqlite import (
    SQLiteContextStore,
    SQLiteRunStore,
    SQLiteRunStoreSync,
    SQLiteWorkspaceStore,
    StateDB,
)
from meridian.lib.config._paths import resolve_repo_root
from meridian.lib.harness.registry import HarnessRegistry, get_default_harness_registry
from meridian.lib.state.artifact_store import LocalStore
from meridian.lib.types import WorkspaceId


@dataclass(frozen=True, slots=True)
class OperationRuntime:
    """Resolved dependencies used by operation handlers."""

    repo_root: Path
    state: StateDB
    run_store_sync: SQLiteRunStoreSync
    run_store: SQLiteRunStore
    workspace_store: SQLiteWorkspaceStore
    context_store: SQLiteContextStore
    harness_registry: HarnessRegistry
    artifacts: LocalStore


def build_runtime(repo_root: str | None = None) -> OperationRuntime:
    """Build a runtime bundle rooted at one repository path."""

    explicit_root = Path(repo_root).expanduser().resolve() if repo_root else None
    resolved_root = resolve_repo_root(explicit_root)
    state = StateDB(resolved_root)
    run_store_sync = SQLiteRunStoreSync(state)
    return OperationRuntime(
        repo_root=resolved_root,
        state=state,
        run_store_sync=run_store_sync,
        run_store=SQLiteRunStore(run_store_sync),
        workspace_store=SQLiteWorkspaceStore(state),
        context_store=SQLiteContextStore(state),
        harness_registry=get_default_harness_registry(),
        artifacts=LocalStore(resolved_root / ".meridian" / "artifacts"),
    )


def resolve_workspace_id(workspace: str | None) -> WorkspaceId | None:
    """Resolve workspace from explicit input or environment."""

    resolved = workspace.strip() if workspace is not None else ""
    if not resolved:
        resolved = os.getenv("MERIDIAN_WORKSPACE_ID", "").strip()
    if not resolved:
        return None
    return WorkspaceId(resolved)


def require_workspace_id(workspace: str | None) -> WorkspaceId:
    """Resolve workspace ID and raise when none is configured."""

    resolved = resolve_workspace_id(workspace)
    if resolved is None:
        raise ValueError(
            "Workspace is required. Pass --workspace or set MERIDIAN_WORKSPACE_ID."
        )
    return resolved
