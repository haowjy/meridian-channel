"""Core frozen domain dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from pathlib import Path

    from meridian.lib.types import (
        ArtifactKey,
        ModelId,
        RunId,
        SpanId,
        TraceId,
        WorkflowEventId,
        WorkspaceId,
    )

RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
WorkspaceState = Literal["active", "paused", "completed", "abandoned"]


def _empty_mapping() -> Mapping[str, Any]:
    return cast("Mapping[str, Any]", {})


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage measured for a run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class RunCreateParams:
    """Input fields for creating a run record."""

    prompt: str
    model: ModelId
    workspace_id: WorkspaceId | None = None


@dataclass(frozen=True, slots=True)
class RunFilters:
    """Run list filter options."""

    workspace_id: WorkspaceId | None = None
    status: RunStatus | None = None


@dataclass(frozen=True, slots=True)
class RunEnrichment:
    """Post-run enrichment payload."""

    usage: TokenUsage = field(default_factory=TokenUsage)
    report_path: Path | None = None


@dataclass(frozen=True, slots=True)
class Run:
    """Run aggregate root."""

    run_id: RunId
    prompt: str
    model: ModelId
    status: RunStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    workspace_id: WorkspaceId | None = None


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Compact run view for list output."""

    run_id: RunId
    status: RunStatus
    model: ModelId
    workspace_id: WorkspaceId | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceCreateParams:
    """Input fields for creating a workspace."""

    name: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceFilters:
    """Workspace list filter options."""

    state: WorkspaceState | None = None


@dataclass(frozen=True, slots=True)
class Workspace:
    """Workspace aggregate root."""

    workspace_id: WorkspaceId
    state: WorkspaceState = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    name: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    """Compact workspace list entry."""

    workspace_id: WorkspaceId
    state: WorkspaceState
    name: str | None = None


@dataclass(frozen=True, slots=True)
class PinnedFile:
    """Pinned context file reference."""

    workspace_id: WorkspaceId
    file_path: str


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Skill index operation summary."""

    indexed_count: int


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """Skill manifest metadata."""

    name: str
    description: str
    tags: tuple[str, ...] = ()
    path: str = ""


@dataclass(frozen=True, slots=True)
class SkillContent:
    """Loaded skill body."""

    name: str
    description: str
    tags: tuple[str, ...]
    content: str
    path: str


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """Event-sourced workflow event."""

    event_id: WorkflowEventId
    workspace_id: WorkspaceId
    event_type: str
    payload: Mapping[str, Any]
    run_id: RunId | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class Span:
    """OpenTelemetry-style trace span."""

    span_id: SpanId
    trace_id: TraceId
    name: str
    kind: str
    started_at: datetime
    parent_id: SpanId | None = None
    ended_at: datetime | None = None
    status: str = "ok"
    attributes: Mapping[str, Any] = field(default_factory=_empty_mapping)


@dataclass(frozen=True, slots=True)
class RunEdge:
    """Dependency edge between two runs."""

    source_run_id: RunId
    target_run_id: RunId
    edge_type: str


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """Metadata record for one run artifact."""

    run_id: RunId
    key: ArtifactKey
    path: Path
    size: int | None = None
