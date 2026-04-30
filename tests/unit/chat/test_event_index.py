import sqlite3
from pathlib import Path

from meridian.lib.chat.event_index import ChatEventIndex
from meridian.lib.chat.event_log import ChatEventLog
from meridian.lib.chat.protocol import ChatEvent


def event(event_type: str, seq: int = 0, **kwargs):
    return ChatEvent(
        type=event_type,
        seq=seq,
        chat_id="c1",
        execution_id="p1",
        timestamp="2026-01-01T00:00:00Z",
        **kwargs,
    )


def test_index_projects_representative_tables(tmp_path: Path) -> None:
    index = ChatEventIndex(tmp_path / "index.sqlite3")
    index.upsert(event("turn.started", seq=0, turn_id="t1"))
    index.upsert(
        event(
            "files.persisted",
            seq=1,
            turn_id="t1",
            payload={"files": [{"path": "a.txt", "action": "modified"}]},
        )
    )
    index.upsert(
        event(
            "checkpoint.created",
            seq=2,
            turn_id="t1",
            payload={"turn_id": "t1", "commit_sha": "abc"},
        )
    )
    index.upsert(
        event(
            "turn.completed",
            seq=3,
            turn_id="t1",
            payload={"token_usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        )
    )
    index.close()

    conn = sqlite3.connect(tmp_path / "index.sqlite3")
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4
    assert conn.execute("SELECT path FROM files").fetchone()[0] == "a.txt"
    assert conn.execute("SELECT status FROM turns WHERE turn_id='t1'").fetchone()[0] == "completed"
    assert conn.execute("SELECT commit_sha FROM checkpoints").fetchone()[0] == "abc"
    assert conn.execute("SELECT total_tokens FROM token_usage").fetchone()[0] == 3
    assert conn.execute("SELECT execution_id FROM spawns").fetchone()[0] == "p1"


def test_rebuild_from_log_restores_queryability(tmp_path: Path) -> None:
    log = ChatEventLog(tmp_path / "history.jsonl")
    log.append(event("files.persisted", payload={"path": "b.txt"}))

    index = ChatEventIndex(tmp_path / "index.sqlite3")
    index.rebuild_from_log(log)
    index.close()

    conn = sqlite3.connect(tmp_path / "index.sqlite3")
    assert conn.execute("SELECT path FROM files").fetchall() == [("b.txt",)]
