import asyncio

import pytest

from meridian.lib.chat.event_log import ChatEventLog
from meridian.lib.chat.event_pipeline import ChatEventPipeline
from meridian.lib.chat.protocol import ChatEvent, utc_now_iso


class Session:
    def __init__(self):
        self.completed = []
        self.died = []

    def on_turn_completed(self, generation=None):
        self.completed.append(generation)

    def on_execution_died(self, generation=None):
        self.died.append(generation)


class Fanout:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def event(kind="turn.started", gen=None):
    payload = {} if gen is None else {"execution_generation": gen}
    return ChatEvent(kind, 0, "c1", "e1", utc_now_iso(), payload=payload)


@pytest.mark.asyncio
async def test_pipeline_persists_before_broadcast_and_callback(tmp_path):
    log_path = tmp_path / "events.jsonl"
    session = Session()
    fanout = Fanout()
    pipeline = ChatEventPipeline(
        "c1",
        ChatEventLog(log_path),
        session,
        fanout=fanout,
    )
    pipeline.start()

    await pipeline.ingest(event("turn.completed", gen=2))
    await asyncio.sleep(0.05)
    await pipeline.stop()

    assert fanout.events[0].seq == 0
    assert session.completed == [2]
    assert [stored.type for stored in ChatEventLog(log_path).read_all()] == [
        "turn.completed"
    ]


@pytest.mark.asyncio
async def test_queue_full_drops_event_and_emits_runtime_warning(tmp_path):
    log_path = tmp_path / "events.jsonl"
    session = Session()
    pipeline = ChatEventPipeline(
        "c1",
        ChatEventLog(log_path),
        session,
        max_queue=1,
    )

    await pipeline.ingest(event("content.delta"))
    await pipeline.ingest(event("content.delta"))
    pipeline.start()
    await asyncio.sleep(0.05)
    await pipeline.stop()

    assert [stored.type for stored in ChatEventLog(log_path).read_all()] == [
        "content.delta"
    ]


@pytest.mark.asyncio
async def test_on_execution_complete_notifies_session(tmp_path):
    session = Session()
    pipeline = ChatEventPipeline(
        "c1",
        ChatEventLog(tmp_path / "events.jsonl"),
        session,
    )

    await pipeline.on_execution_complete(3)

    assert session.died == [3]
