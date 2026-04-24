from __future__ import annotations

from typing import Any, cast

import pytest

from meridian.lib.app.agui_replay import replay_events_to_agui
from meridian.lib.core.types import HarnessId
from meridian.lib.streaming.drain_policy import TURN_BOUNDARY_EVENT_TYPE


def _event_types(events: list[Any]) -> list[str]:
    return [cast("str", event.type) for event in events]


def test_replay_from_seq_zero_emits_run_boundaries_and_translated_events() -> None:
    raw_events = [
        {
            "seq": 0,
            "byte_offset": 0,
            "event_type": "item/agentMessage",
            "harness_id": "codex",
            "payload": {"text": "hello"},
        }
    ]

    events = list(replay_events_to_agui(raw_events, HarnessId.CODEX, "p1"))

    assert _event_types(events) == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "RUN_FINISHED",
    ]


def test_replay_turn_boundary_emits_new_run_started_and_finished_pairs() -> None:
    raw_events = [
        {"event_type": "item/agentMessage", "harness_id": "codex", "payload": {"text": "one"}},
        {"event_type": TURN_BOUNDARY_EVENT_TYPE, "harness_id": "codex", "payload": {}},
        {"event_type": "item/agentMessage", "harness_id": "codex", "payload": {"text": "two"}},
    ]

    events = list(replay_events_to_agui(raw_events, HarnessId.CODEX, "p1"))

    assert _event_types(events) == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "RUN_FINISHED",
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "RUN_FINISHED",
    ]


def test_replay_run_error_suppresses_terminal_run_finished() -> None:
    raw_events = [
        {
            "event_type": "error/connectionClosed",
            "harness_id": "codex",
            "payload": {"message": "boom"},
        }
    ]

    events = list(replay_events_to_agui(raw_events, HarnessId.CODEX, "p1"))

    assert _event_types(events) == ["RUN_STARTED", "RUN_ERROR"]


def test_replay_skips_invalid_raw_events() -> None:
    raw_events: list[dict[str, Any]] = [
        {"payload": {"text": "missing-required-fields"}},
        {
            "event": {
                "event_type": "item/agentMessage",
                "harness_id": "codex",
                "payload": {"text": "wrapped"},
            }
        },
        {"event_type": "item/agentMessage", "harness_id": "codex", "payload": "not-a-dict"},
    ]

    events = list(replay_events_to_agui(raw_events, HarnessId.CODEX, "p1"))

    assert _event_types(events) == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "RUN_FINISHED",
    ]


@pytest.mark.parametrize(
    ("harness_id", "raw_event"),
    [
        (
            HarnessId.CLAUDE,
            {
                "event_type": "assistant",
                "harness_id": "claude",
                "payload": {
                    "content": [{"type": "text", "text": "hello from claude"}],
                },
            },
        ),
        (
            HarnessId.CODEX,
            {
                "event_type": "item/agentMessage",
                "harness_id": "codex",
                "payload": {"item": {"type": "agentMessage", "text": "hello from codex"}},
            },
        ),
        (
            HarnessId.OPENCODE,
            {
                "event_type": "message.updated",
                "harness_id": "opencode",
                "payload": {
                    "properties": {
                        "info": {
                            "id": "msg-1",
                            "role": "assistant",
                            "content": "hello from opencode",
                        }
                    }
                },
            },
        ),
    ],
)
def test_replay_with_harness_fixture_shapes(
    harness_id: HarnessId,
    raw_event: dict[str, Any],
) -> None:
    events = list(replay_events_to_agui([raw_event], harness_id, "p-fixture"))

    event_types = _event_types(events)
    assert event_types[0] == "RUN_STARTED"
    assert event_types[-1] == "RUN_FINISHED"
    assert len(event_types) >= 3
