"""Core frozen domain dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from pathlib import Path

    from meridian.lib.formatting import FormatContext
    from meridian.lib.types import (
        ArtifactKey,
        ModelId,
        RunId,
        SpanId,
        TraceId,
        WorkflowEventId,
        SpaceId,
    )

RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
SpaceState = Literal["active", "closed"]


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
    space_id: SpaceId | None = None


@dataclass(frozen=True, slots=True)
class RunFilters:
    """Run list filter options."""

    space_id: SpaceId | None = None
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
    space_id: SpaceId | None = None


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Compact run view for list output."""

    run_id: RunId
    status: RunStatus
    model: ModelId
    space_id: SpaceId | None = None


@dataclass(frozen=True, slots=True)
class SpaceCreateParams:
    """Input fields for creating a space."""

    name: str | None = None


@dataclass(frozen=True, slots=True)
class SpaceFilters:
    """Space list filter options."""

    state: SpaceState | None = None


@dataclass(frozen=True, slots=True)
class Space:
    """Space aggregate root."""

    space_id: SpaceId
    state: SpaceState = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class SpaceSummary:
    """Compact space list entry."""

    space_id: SpaceId
    state: SpaceState
    finished_at: datetime | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class PinnedFile:
    """Pinned context file reference."""

    space_id: SpaceId
    file_path: str


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Skill index operation summary."""

    indexed_count: int

    def format_text(self, ctx: FormatContext | None = None) -> str:
        return f"skills.reindex  ok  indexed={self.indexed_count}"


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

    def format_text(self, ctx: FormatContext | None = None) -> str:
        return f"{self.name}: {self.description}\n\n{self.content}"


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """Event-sourced workflow event."""

    event_id: WorkflowEventId
    space_id: SpaceId
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
