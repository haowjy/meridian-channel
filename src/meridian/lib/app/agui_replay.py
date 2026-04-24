"""AG-UI event replay from raw harness event sequences."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, cast

from ag_ui.core import BaseEvent
from meridian.lib.app.agui_mapping import get_agui_mapper
from meridian.lib.core.types import HarnessId
from meridian.lib.harness.connections.base import HarnessEvent
from meridian.lib.streaming.drain_policy import TURN_BOUNDARY_EVENT_TYPE


def replay_events_to_agui(
    raw_events: list[dict[str, Any]],
    harness_id: HarnessId,
    spawn_id: str,
) -> Iterator[BaseEvent]:
    """Replay raw harness events through a fresh mapper to produce AG-UI events.

    Args:
        raw_events: Raw event dictionaries, seq-enveloped or already stripped.
        harness_id: Harness identifier selecting the mapper.
        spawn_id: Spawn ID used for run started/finished events.

    Yields:
        AG-UI events in order, with run lifecycle boundaries.
    """

    mapper = get_agui_mapper(harness_id)

    yield mapper.make_run_started(spawn_id)

    turn_active = True
    error_emitted = False

    for raw_event in raw_events:
        event = _raw_to_harness_event(raw_event)
        if event is None:
            continue

        if event.event_type == TURN_BOUNDARY_EVENT_TYPE:
            if turn_active and not error_emitted:
                yield mapper.make_run_finished(spawn_id)
            turn_active = False
            error_emitted = False
            continue

        if not turn_active:
            yield mapper.make_run_started(spawn_id)
            turn_active = True

        for translated in mapper.translate(event):
            yield translated
            if getattr(translated, "type", None) == "RUN_ERROR":
                error_emitted = True

    if turn_active and not error_emitted:
        yield mapper.make_run_finished(spawn_id)


def _raw_to_harness_event(raw: dict[str, Any]) -> HarnessEvent | None:
    """Convert one raw history event dictionary into a HarnessEvent."""

    base: Mapping[str, object] = raw
    nested = raw.get("event")
    if isinstance(nested, Mapping):
        base = cast("Mapping[str, object]", nested)

    event_type_obj = base.get("event_type")
    if not isinstance(event_type_obj, str):
        return None

    harness_id_obj = base.get("harness_id")
    if not isinstance(harness_id_obj, str):
        outer_harness = raw.get("harness_id")
        if not isinstance(outer_harness, str):
            return None
        harness_id_obj = outer_harness

    payload_obj = base.get("payload")
    payload: dict[str, object]
    if isinstance(payload_obj, Mapping):
        payload_map = cast("Mapping[object, object]", payload_obj)
        payload = {str(key): value for key, value in payload_map.items()}
    else:
        payload = {}

    raw_text_obj = base.get("raw_text")
    raw_text: str | None
    if isinstance(raw_text_obj, str):
        raw_text = raw_text_obj
    else:
        outer_raw_text = raw.get("raw_text")
        raw_text = outer_raw_text if isinstance(outer_raw_text, str) else None

    return HarnessEvent(
        event_type=event_type_obj,
        harness_id=harness_id_obj,
        payload=payload,
        raw_text=raw_text,
    )


__all__ = ["replay_events_to_agui"]
