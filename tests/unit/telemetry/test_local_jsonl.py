from __future__ import annotations

import json
import os

from meridian.lib.telemetry.events import TelemetryEnvelope
from meridian.lib.telemetry.local_jsonl import LocalJSONLSink


def envelope(event: str = "chat.ws.connected") -> TelemetryEnvelope:
    return TelemetryEnvelope(
        v=1,
        ts="2026-05-02T12:00:00Z",
        domain="chat",
        event=event,
        scope="chat.server.ws",
        severity="info",
        ids={"chat_id": "c1"},
    )


def test_write_batch_creates_pid_owned_segment_with_json_lines(tmp_path) -> None:
    sink = LocalJSONLSink(tmp_path)
    sink.write_batch([envelope()])
    sink.close()

    segment = tmp_path / "telemetry" / f"{os.getpid()}-0001.jsonl"
    assert segment.exists()
    lines = segment.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "chat.ws.connected"


def test_rotation_opens_next_segment_without_renaming_active_file(tmp_path) -> None:
    sink = LocalJSONLSink(tmp_path, max_segment_bytes=1)
    sink.write_batch([envelope()])
    first = tmp_path / "telemetry" / f"{os.getpid()}-0001.jsonl"
    second = tmp_path / "telemetry" / f"{os.getpid()}-0002.jsonl"

    assert first.exists()
    assert second.exists()
    payload = json.loads(first.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "chat.ws.connected"
    sink.close()


def test_close_is_idempotent(tmp_path) -> None:
    sink = LocalJSONLSink(tmp_path)
    sink.write_batch([envelope()])
    sink.close()
    sink.close()
