"""AG-UI mapper registry and default passthrough implementation."""

from __future__ import annotations

from meridian.lib.app.agui_mapping.base import AGUIMapper
from meridian.lib.app.agui_types import (
    BaseEvent,
    HarnessEventEnvelopeEvent,
    RunFinishedEvent,
    RunStartedEvent,
)
from meridian.lib.core.types import HarnessId
from meridian.lib.harness.connections.base import HarnessEvent


class _PassthroughAGUIMapper:
    """MVP mapper: wraps raw harness events without semantic translation."""

    def translate(self, event: HarnessEvent) -> list[BaseEvent]:
        return [
            HarnessEventEnvelopeEvent(
                harness_id=event.harness_id,
                event_type=event.event_type,
                payload=event.payload,
                raw_text=event.raw_text,
            )
        ]

    def make_run_started(self, spawn_id: str) -> RunStartedEvent:
        return RunStartedEvent(run_id=spawn_id)

    def make_run_finished(self, spawn_id: str) -> RunFinishedEvent:
        return RunFinishedEvent(run_id=spawn_id, status="completed")


_MAPPER_REGISTRY: dict[HarnessId, AGUIMapper] = {}
_DEFAULT_MAPPER: AGUIMapper = _PassthroughAGUIMapper()


def register_agui_mapper(harness_id: HarnessId, mapper: AGUIMapper) -> None:
    """Register one AG-UI mapper for a specific harness."""

    _MAPPER_REGISTRY[harness_id] = mapper


def get_agui_mapper(harness_id: HarnessId) -> AGUIMapper:
    """Return the AG-UI mapper for one harness, falling back to passthrough."""

    return _MAPPER_REGISTRY.get(harness_id, _DEFAULT_MAPPER)


__all__ = ["AGUIMapper", "get_agui_mapper", "register_agui_mapper"]
