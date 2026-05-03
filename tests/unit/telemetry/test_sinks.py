from __future__ import annotations

import threading
from collections.abc import Sequence

from meridian.lib.telemetry.events import TelemetryEnvelope
from meridian.lib.telemetry.sinks import BufferingSink


def _envelope(event: str) -> TelemetryEnvelope:
    return TelemetryEnvelope(
        v=1,
        ts="2026-05-02T12:00:00Z",
        domain="usage",
        event=event,
        scope="cli.dispatch",
    )


class _RecordingSink:
    def __init__(self, *, block_first_write: bool = False) -> None:
        self.events: list[list[str]] = []
        self.closed = False
        self._block_first_write = block_first_write
        self._entered = threading.Event()
        self._release = threading.Event()
        self._writes = 0

    @property
    def entered(self) -> threading.Event:
        return self._entered

    @property
    def release(self) -> threading.Event:
        return self._release

    def write_batch(self, events: Sequence[TelemetryEnvelope]) -> None:
        self._writes += 1
        self._entered.set()
        if self._block_first_write and self._writes == 1:
            assert self._release.wait(timeout=1.0)
        self.events.append([event.event for event in events])

    def close(self) -> None:
        self.closed = True


def test_buffering_sink_replays_buffer_then_forwards_future_batches() -> None:
    sink = BufferingSink()
    sink.write_batch([_envelope("usage.command.invoked")])
    sink.write_batch([_envelope("usage.model.selected")])

    real_sink = _RecordingSink()
    sink.upgrade(real_sink)
    sink.write_batch([_envelope("usage.spawn.launched")])

    assert real_sink.events == [
        ["usage.command.invoked", "usage.model.selected"],
        ["usage.spawn.launched"],
    ]


def test_buffering_sink_keeps_only_most_recent_buffered_events() -> None:
    sink = BufferingSink(max_buffer=2)
    sink.write_batch([_envelope("usage.command.invoked")])
    sink.write_batch([_envelope("usage.model.selected")])
    sink.write_batch([_envelope("usage.spawn.launched")])

    real_sink = _RecordingSink()
    sink.upgrade(real_sink)

    assert real_sink.events == [["usage.model.selected", "usage.spawn.launched"]]


def test_buffering_sink_upgrade_serializes_concurrent_write_handoff() -> None:
    sink = BufferingSink()
    sink.write_batch([_envelope("usage.command.invoked")])
    real_sink = _RecordingSink(block_first_write=True)

    upgrade_thread = threading.Thread(target=sink.upgrade, args=(real_sink,))
    upgrade_thread.start()
    assert real_sink.entered.wait(timeout=1.0)

    write_finished = threading.Event()

    def _write_live_batch() -> None:
        sink.write_batch([_envelope("usage.spawn.launched")])
        write_finished.set()

    writer_thread = threading.Thread(target=_write_live_batch)
    writer_thread.start()

    assert not write_finished.wait(timeout=0.05)
    real_sink.release.set()

    upgrade_thread.join(timeout=1.0)
    writer_thread.join(timeout=1.0)

    assert write_finished.is_set()
    assert real_sink.events == [
        ["usage.command.invoked"],
        ["usage.spawn.launched"],
    ]


def test_buffering_sink_close_forwards_only_after_upgrade() -> None:
    sink = BufferingSink()
    sink.close()

    real_sink = _RecordingSink()
    sink.upgrade(real_sink)
    sink.close()

    assert real_sink.closed is True
