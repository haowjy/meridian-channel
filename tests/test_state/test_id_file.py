
import json

from meridian.lib.state.spawn_store import next_spawn_id, next_chat_id


def test_next_run_id_counts_start_events_and_skips_truncated_trailing_line(tmp_path):
    spawns_jsonl = tmp_path / "spawns.jsonl"
    with spawns_jsonl.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"v": 1, "event": "start", "id": "r1"}) + "\n")
        handle.write(json.dumps({"v": 1, "event": "finalize", "id": "r1"}) + "\n")
        handle.write(json.dumps({"v": 1, "event": "start", "id": "r2"}) + "\n")
        handle.write('{"v":1,"event":"start","id":"r3"')

    assert next_spawn_id(tmp_path) == "p3"


def test_next_chat_id_counts_start_events(tmp_path):
    sessions_jsonl = tmp_path / "sessions.jsonl"
    with sessions_jsonl.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"v": 1, "event": "start", "chat_id": "c1"}) + "\n")
        handle.write(json.dumps({"v": 1, "event": "stop", "chat_id": "c1"}) + "\n")
        handle.write(json.dumps({"v": 1, "event": "start", "chat_id": "c2"}) + "\n")

    assert next_chat_id(tmp_path) == "c3"
