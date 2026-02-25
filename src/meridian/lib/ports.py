"""Storage protocol interfaces for dependency inversion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from meridian.lib.domain import (
        IndexReport,
        PinnedFile,
        Run,
        RunCreateParams,
        RunEnrichment,
        RunFilters,
        RunStatus,
        RunSummary,
        SkillContent,
        SkillManifest,
        Workspace,
        WorkspaceCreateParams,
        WorkspaceFilters,
        WorkspaceState,
        WorkspaceSummary,
    )
    from meridian.lib.types import RunId, WorkspaceId


class RunStore(Protocol):
    """Async read/write interface for run data (MCP path)."""

    async def create(self, params: RunCreateParams) -> Run: ...

    async def get(self, run_id: RunId) -> Run | None: ...

    async def list(self, filters: RunFilters) -> list[RunSummary]: ...

    async def update_status(self, run_id: RunId, status: RunStatus) -> None: ...

    async def enrich(self, run_id: RunId, enrichment: RunEnrichment) -> None: ...


class RunStoreSync(Protocol):
    """Sync read/write interface for run data (CLI path)."""

    def create(self, params: RunCreateParams) -> Run: ...

    def get(self, run_id: RunId) -> Run | None: ...

    def list(self, filters: RunFilters) -> list[RunSummary]: ...

    def update_status(self, run_id: RunId, status: RunStatus) -> None: ...

    def enrich(self, run_id: RunId, enrichment: RunEnrichment) -> None: ...


class WorkspaceStore(Protocol):
    """Async workspace storage interface."""

    async def create(self, params: WorkspaceCreateParams) -> Workspace: ...

    async def get(self, workspace_id: WorkspaceId) -> Workspace | None: ...

    async def list(self, filters: WorkspaceFilters) -> list[WorkspaceSummary]: ...

    async def transition(self, workspace_id: WorkspaceId, new_state: WorkspaceState) -> None: ...


class SkillIndex(Protocol):
    """Async skill index interface."""

    async def reindex(self, skills_dir: Path) -> IndexReport: ...

    async def search(self, query: str) -> list[SkillManifest]: ...

    async def load(self, names: list[str]) -> list[SkillContent]: ...


class ContextStore(Protocol):
    """Pinned context storage interface."""

    async def pin(self, workspace_id: WorkspaceId, file_path: str) -> None: ...

    async def unpin(self, workspace_id: WorkspaceId, file_path: str) -> None: ...

    async def list_pinned(self, workspace_id: WorkspaceId) -> list[PinnedFile]: ...
