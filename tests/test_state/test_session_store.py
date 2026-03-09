import json

from meridian.lib.state.session_store import cleanup_stale_sessions, start_session, stop_session


def _state_root(tmp_path):
    state_dir = tmp_path / ".meridian"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def test_cleanup_stale_sessions_removes_dead_locks_and_writes_stop_events(tmp_path):
    state_root = _state_root(tmp_path)
    live = start_session(
        state_root,
        harness="codex",
        harness_session_id="live-thread",
        model="gpt-5.3-codex",
    )

    stale_lock = state_root / "sessions" / "c2.lock"
    stale_lock.parent.mkdir(parents=True, exist_ok=True)
    stale_lock.touch()

    with (state_root / "sessions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "v": 1,
                    "event": "start",
                    "chat_id": "c2",
                    "harness": "claude",
                    "harness_session_id": "stale-thread",
                    "model": "claude-opus-4-6",
                    "params": [],
                    "started_at": "2026-03-01T00:00:00Z",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )

    cleanup = cleanup_stale_sessions(state_root)
    assert cleanup.cleaned_ids == ("c2",)
    assert cleanup.materialized_scopes == (("claude", "c2"),)
    assert not stale_lock.exists()
    assert (state_root / "sessions" / f"{live}.lock").exists()

    rows = [
        json.loads(line)
        for line in (state_root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    stop_rows = [row for row in rows if row.get("event") == "stop" and row.get("chat_id") == "c2"]
    assert len(stop_rows) == 1
    assert stop_rows[0]["v"] == 1
    assert isinstance(stop_rows[0]["stopped_at"], str)

    stop_session(state_root, live)
