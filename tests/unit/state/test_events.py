from __future__ import annotations

import pytest

from meridian.lib.state.spawn.events import reduce_events
from meridian.lib.state.spawn_store import (
    SpawnExitedEvent,
    SpawnFinalizeEvent,
    SpawnStartEvent,
    SpawnUpdateEvent,
)


@pytest.mark.unit
def test_reduce_events_empty_list_returns_empty_mapping() -> None:
    assert reduce_events([]) == {}


@pytest.mark.unit
def test_reduce_events_single_start_event_creates_record() -> None:
    records = reduce_events(
        [
            SpawnStartEvent(
                id="p1",
                chat_id="chat-1",
                model="gpt-5",
                agent="coder",
                harness="codex",
                prompt="run",
            )
        ]
    )

    assert list(records) == ["p1"]
    record = records["p1"]
    assert record.status == "running"
    assert record.chat_id == "chat-1"
    assert record.model == "gpt-5"


@pytest.mark.unit
def test_reduce_events_update_event_modifies_record() -> None:
    records = reduce_events(
        [
            SpawnStartEvent(
                id="p1",
                chat_id="chat-1",
                model="gpt-5",
                agent="coder",
                harness="codex",
                prompt="run",
            ),
            SpawnUpdateEvent(
                id="p1",
                status="finalizing",
                desc="updated",
                work_id="  w42  ",
            ),
        ]
    )

    record = records["p1"]
    assert record.status == "finalizing"
    assert record.desc == "updated"
    assert record.work_id == "w42"


@pytest.mark.unit
def test_reduce_events_exited_event_records_process_exit_code() -> None:
    records = reduce_events(
        [
            SpawnStartEvent(
                id="p1",
                chat_id="chat-1",
                model="gpt-5",
                agent="coder",
                harness="codex",
                prompt="run",
            ),
            SpawnExitedEvent(id="p1", exit_code=17, exited_at="2026-04-19T12:00:00+00:00"),
        ]
    )

    record = records["p1"]
    assert record.process_exit_code == 17
    assert record.exited_at == "2026-04-19T12:00:00+00:00"


@pytest.mark.unit
def test_reduce_events_finalize_event_sets_terminal_state() -> None:
    records = reduce_events(
        [
            SpawnStartEvent(
                id="p1",
                chat_id="chat-1",
                model="gpt-5",
                agent="coder",
                harness="codex",
                prompt="run",
            ),
            SpawnFinalizeEvent(
                id="p1",
                status="succeeded",
                exit_code=0,
                finished_at="2026-04-19T12:01:00+00:00",
                origin="runner",
            ),
        ]
    )

    record = records["p1"]
    assert record.status == "succeeded"
    assert record.exit_code == 0
    assert record.finished_at == "2026-04-19T12:01:00+00:00"
    assert record.terminal_origin == "runner"


@pytest.mark.unit
def test_reduce_events_multiple_events_for_same_spawn_merge() -> None:
    records = reduce_events(
        [
            SpawnStartEvent(
                id="p1",
                chat_id="chat-1",
                model="gpt-5",
                agent="coder",
                harness="codex",
                prompt="run",
            ),
            SpawnUpdateEvent(id="p1", desc="step-1"),
            SpawnExitedEvent(id="p1", exit_code=7, exited_at="2026-04-19T12:02:00+00:00"),
            SpawnFinalizeEvent(
                id="p1",
                status="failed",
                exit_code=1,
                finished_at="2026-04-19T12:03:00+00:00",
                error="boom",
                origin="runner",
            ),
        ]
    )

    record = records["p1"]
    assert record.status == "failed"
    assert record.desc == "step-1"
    assert record.process_exit_code == 7
    assert record.exit_code == 1
    assert record.error == "boom"


@pytest.mark.unit
def test_reduce_events_events_for_different_spawns_stay_separate() -> None:
    records = reduce_events(
        [
            SpawnStartEvent(
                id="p1",
                chat_id="chat-1",
                model="gpt-5",
                agent="coder",
                harness="codex",
                prompt="run",
            ),
            SpawnStartEvent(
                id="p2",
                chat_id="chat-2",
                model="gpt-5-mini",
                agent="reviewer",
                harness="codex",
                prompt="review",
            ),
            SpawnFinalizeEvent(
                id="p2",
                status="cancelled",
                exit_code=130,
                error="cancelled",
                origin="runner",
            ),
        ]
    )

    assert set(records) == {"p1", "p2"}
    assert records["p1"].status == "running"
    assert records["p2"].status == "cancelled"
