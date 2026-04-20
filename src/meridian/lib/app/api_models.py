"""Shared API models for Meridian app endpoints."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class CursorEnvelope(BaseModel, Generic[T]):
    """Generic cursor pagination wrapper."""

    model_config = ConfigDict(frozen=True)

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class SpawnProjection(BaseModel):
    """Dashboard-ready spawn projection."""

    model_config = ConfigDict(frozen=True)

    spawn_id: str
    status: str
    harness: str = ""
    model: str = ""
    agent: str = ""
    work_id: str | None = None
    desc: str = ""
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class SpawnStatsProjection(BaseModel):
    """Aggregated spawn status counts for dashboard."""

    model_config = ConfigDict(frozen=True)

    running: int = 0
    queued: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    finalizing: int = 0
    total: int = 0


class WorkProjection(BaseModel):
    """Work item projection for dashboard."""

    model_config = ConfigDict(frozen=True)

    work_id: str
    name: str
    status: str
    description: str = ""
    work_dir: str = ""
    created_at: str = ""
    last_activity_at: str | None = None
    spawn_count: int = 0
    session_count: int = 0


class SSEEvent(BaseModel):
    """Wrapper for SSE event payloads."""

    model_config = ConfigDict(frozen=True)

    event_type: str
    data: dict[str, object]


class AgentSummary(BaseModel):
    """Summary projection of an agent profile for the launch UI."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    model: str | None = None
    harness: str | None = None
    skills: list[str] = []
    path: str = ""


class EventRecord(BaseModel):
    """Raw event record from the persisted output artifact."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    spawn_id: str
    line_index: int
    payload: dict[str, object]


class ToolCallRecord(BaseModel):
    """Tool call record extracted from a persisted output artifact."""

    model_config = ConfigDict(frozen=True)

    call_id: str
    spawn_id: str
    line_index: int
    payload: dict[str, object]


class TokenUsageResponse(BaseModel):
    """Token usage summary for a thread/spawn."""

    model_config = ConfigDict(frozen=True)

    spawn_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None


__all__ = [
    "AgentSummary",
    "CursorEnvelope",
    "EventRecord",
    "SSEEvent",
    "SpawnProjection",
    "SpawnStatsProjection",
    "TokenUsageResponse",
    "ToolCallRecord",
    "WorkProjection",
]
