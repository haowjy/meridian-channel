from __future__ import annotations

import time
from collections.abc import Sequence

from meridian.lib.telemetry import emit_telemetry, init_telemetry
from meridian.lib.telemetry.events import TelemetryEnvelope
from meridian.lib.telemetry.router import TelemetryRouter


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[TelemetryEnvelope] = []

    def write_batch(self, events: Sequence[TelemetryEnvelope]) -> None:
        self.events.extend(events)

    def close(self) -> None:
        pass


class FailingSink:
    def write_batch(self, events: Sequence[TelemetryEnvelope]) -> None:
        _ = events
        raise RuntimeError("sink broke")

    def close(self) -> None:
        pass


def wait_for(predicate: object, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.01)
    raise AssertionError("condition not met")


def test_non_blocking_enqueue_and_background_write() -> None:
    sink = RecordingSink()
    router = TelemetryRouter(sink, flush_interval_secs=0.01)
    router.emit("chat", "chat.ws.connected", scope="chat.server.ws", ids={"chat_id": "c1"})
    wait_for(lambda: len(sink.events) == 1)
    assert sink.events[0].event == "chat.ws.connected"
    router.close()


def test_global_emit_never_raises_on_invalid_event_or_sink_failure() -> None:
    init_telemetry(sink=FailingSink())
    emit_telemetry("chat", "not.registered", scope="test")
    emit_telemetry("chat", "chat.ws.connected", scope="test")


def test_sink_write_batch_called_by_global_writer() -> None:
    sink = RecordingSink()
    init_telemetry(sink=sink)
    emit_telemetry("usage", "usage.command.invoked", scope="cli.dispatch")
    wait_for(lambda: len(sink.events) == 1)
    assert sink.events[0].to_dict()["event"] == "usage.command.invoked"


def test_error_severity_wakes_writer_promptly() -> None:
    sink = RecordingSink()
    router = TelemetryRouter(sink, flush_interval_secs=10.0)
    router.emit(
        "runtime",
        "runtime.telemetry.sink_failed",
        scope="telemetry.router",
        severity="error",
        data={"error": {"message": "x"}},
    )
    wait_for(lambda: len(sink.events) == 1)
    assert sink.events[0].severity == "error"
    router.close()
