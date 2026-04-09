"""Minimal AG-UI event models used by the WebSocket bridge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class BaseEvent(BaseModel):
    """Base AG-UI event payload."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RunStartedEvent(BaseEvent):
    """Event emitted when a run starts streaming."""

    type: Literal["RUN_STARTED"] = "RUN_STARTED"
    run_id: str


class RunFinishedEvent(BaseEvent):
    """Event emitted when a run completes."""

    type: Literal["RUN_FINISHED"] = "RUN_FINISHED"
    run_id: str
    status: str | None = None


class RunErrorEvent(BaseEvent):
    """Event emitted for transport or protocol errors."""

    type: Literal["RUN_ERROR"] = "RUN_ERROR"
    message: str


class TextMessageStartEvent(BaseEvent):
    """Event marking the beginning of one text message."""

    type: Literal["TEXT_MESSAGE_START"] = "TEXT_MESSAGE_START"
    message_id: str
    role: str = "assistant"


class TextMessageContentEvent(BaseEvent):
    """Event carrying one text chunk."""

    type: Literal["TEXT_MESSAGE_CONTENT"] = "TEXT_MESSAGE_CONTENT"
    message_id: str
    text: str


class TextMessageEndEvent(BaseEvent):
    """Event marking the end of one text message."""

    type: Literal["TEXT_MESSAGE_END"] = "TEXT_MESSAGE_END"
    message_id: str


class HarnessEventEnvelopeEvent(BaseEvent):
    """Temporary passthrough event until harness-specific AG-UI mapping lands."""

    type: Literal["HARNESS_EVENT"] = "HARNESS_EVENT"
    harness_id: str
    event_type: str
    payload: dict[str, object]
    raw_text: str | None = None


__all__ = [
    "BaseEvent",
    "HarnessEventEnvelopeEvent",
    "RunErrorEvent",
    "RunFinishedEvent",
    "RunStartedEvent",
    "TextMessageContentEvent",
    "TextMessageEndEvent",
    "TextMessageStartEvent",
]
