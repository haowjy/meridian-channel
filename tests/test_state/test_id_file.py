import json

from meridian.lib.state.spawn_store import next_spawn_id


def test_next_run_id_counts_start_events_and_skips_truncated_trailing_line(tmp_path):
    spawns_jsonl = tmp_path / "spawns.jsonl"
    with spawns_jsonl.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"v": 1, "event": "start", "id": "r1"}) + "\n")
        handle.write(json.dumps({"v": 1, "event": "finalize", "id": "r1"}) + "\n")
        handle.write(json.dumps({"v": 1, "event": "start", "id": "r2"}) + "\n")
        handle.write('{"v":1,"event":"start","id":"r3"')

    assert next_spawn_id(tmp_path) == "p3"
