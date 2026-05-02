from __future__ import annotations

import json
import os
import time

from meridian.lib.telemetry import emit_telemetry
from meridian.lib.telemetry.init import setup_telemetry
from meridian.lib.telemetry.retention import run_retention_cleanup


def wait_for(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met")


def test_retention_cleanup_deletes_old_orphaned_files(tmp_path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    old = telemetry_dir / "999999-0001.jsonl"
    old.write_text('{"event":"old"}\n', encoding="utf-8")
    old_time = time.time() - 10 * 24 * 60 * 60
    os.utime(old, (old_time, old_time))

    run_retention_cleanup(telemetry_dir, max_age_days=7)

    assert not old.exists()


def test_retention_preserves_files_from_live_processes(tmp_path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    live = telemetry_dir / f"{os.getpid()}-0001.jsonl"
    live.write_text('{"event":"live"}\n', encoding="utf-8")
    old_time = time.time() - 10 * 24 * 60 * 60
    os.utime(live, (old_time, old_time))

    run_retention_cleanup(telemetry_dir, max_age_days=7, max_total_bytes=1)

    assert live.exists()


def test_full_pipeline_emit_queue_writer_segment(tmp_path) -> None:
    setup_telemetry(runtime_root=tmp_path)
    emit_telemetry("chat", "chat.ws.connected", scope="chat.server.ws", ids={"chat_id": "c1"})

    segment = tmp_path / "telemetry" / f"{os.getpid()}-0001.jsonl"
    wait_for(lambda: segment.exists() and segment.read_text(encoding="utf-8"))
    event = json.loads(segment.read_text(encoding="utf-8").splitlines()[0])
    assert event["event"] == "chat.ws.connected"
    assert event["ids"] == {"chat_id": "c1"}
