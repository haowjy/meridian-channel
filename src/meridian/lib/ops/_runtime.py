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
from meridian.lib.config.settings import MeridianConfig, load_config
from meridian.lib.harness.registry import HarnessRegistry, get_default_harness_registry
from meridian.lib.state.artifact_store import LocalStore
from meridian.lib.types import WorkspaceId


@dataclass(frozen=True, slots=True)
class OperationRuntime:
    """Resolved dependencies used by operation handlers."""

    repo_root: Path
    config: MeridianConfig
    state: StateDB
    run_store_sync: SQLiteRunStoreSync
    run_store: SQLiteRunStore
    workspace_store: SQLiteWorkspaceStore
    context_store: SQLiteContextStore
    harness_registry: HarnessRegistry
    artifacts: LocalStore


def resolve_runtime_root_and_config(
    repo_root: str | None = None,
) -> tuple[Path, MeridianConfig]:
    """Resolve repository root and load operational config."""

    explicit_root = Path(repo_root).expanduser().resolve() if repo_root else None
    resolved_root = resolve_repo_root(explicit_root)
    return resolved_root, load_config(resolved_root)


def build_runtime_from_root_and_config(
    repo_root: Path,
    config: MeridianConfig,
) -> OperationRuntime:
    """Build a runtime bundle from one pre-resolved root and config."""

    state = StateDB(repo_root)
    run_store_sync = SQLiteRunStoreSync(state)
    return OperationRuntime(
        repo_root=repo_root,
        config=config,
        state=state,
        run_store_sync=run_store_sync,
        run_store=SQLiteRunStore(run_store_sync),
        workspace_store=SQLiteWorkspaceStore(state),
        context_store=SQLiteContextStore(state),
        harness_registry=get_default_harness_registry(),
        artifacts=LocalStore(repo_root / ".meridian" / "artifacts"),
    )


def build_runtime(repo_root: str | None = None) -> OperationRuntime:
    """Build a runtime bundle rooted at one repository path."""

    resolved_root, config = resolve_runtime_root_and_config(repo_root)
    return build_runtime_from_root_and_config(resolved_root, config)


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
