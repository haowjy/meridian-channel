import asyncio

import pytest

from meridian.lib.chat.event_log import ChatEventLog
from meridian.lib.chat.event_pipeline import ChatEventPipeline
from meridian.lib.chat.protocol import ChatEvent, utc_now_iso


class RecordingFanout:
    def __init__(self, log_path):
        self.log_path = log_path
        self.saw_persisted = []

    async def broadcast(self, event):
        lines = self.log_path.read_text().splitlines()
        self.saw_persisted.append(any(f'"seq":{event.seq}' in line for line in lines))


class Session:
    def __init__(self):
        self.completed = False

    def on_turn_completed(self, generation=None):
        self.completed = True

    def on_execution_died(self, generation=None):
        pass


@pytest.mark.asyncio
async def test_persist_before_broadcast_before_callback(tmp_path):
    path = tmp_path / "events.jsonl"
    fanout = RecordingFanout(path)
    session = Session()
    pipeline = ChatEventPipeline("c1", ChatEventLog(path), session, fanout=fanout)
    pipeline.start()

    await pipeline.ingest(ChatEvent("turn.completed", 0, "c1", "e1", utc_now_iso()))
    await asyncio.sleep(0.05)
    await pipeline.stop()

    assert fanout.saw_persisted == [True]
    assert session.completed
