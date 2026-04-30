"""Derived SQLite projections for chat event logs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from meridian.lib.chat.event_log import ChatEventLog
from meridian.lib.chat.protocol import ChatEvent


class ChatEventIndex:
    """Rebuildable SQLite projection over the JSONL ChatEvent source of truth."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        chat_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        type TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        turn_id TEXT,
        item_id TEXT,
        request_id TEXT,
        harness_id TEXT,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (chat_id, seq)
    );
    CREATE INDEX IF NOT EXISTS idx_events_type ON events(chat_id, type, seq);

    CREATE TABLE IF NOT EXISTS files (
        chat_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        path TEXT NOT NULL,
        action TEXT,
        turn_id TEXT,
        execution_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (chat_id, seq, path)
    );

    CREATE TABLE IF NOT EXISTS turns (
        chat_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        started_seq INTEGER,
        completed_seq INTEGER,
        started_at TEXT,
        completed_at TEXT,
        status TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (chat_id, turn_id)
    );

    CREATE TABLE IF NOT EXISTS checkpoints (
        chat_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        created_seq INTEGER,
        reverted_seq INTEGER,
        created_at TEXT,
        reverted_at TEXT,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (chat_id, turn_id, commit_sha)
    );

    CREATE TABLE IF NOT EXISTS token_usage (
        chat_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        turn_id TEXT,
        execution_id TEXT NOT NULL,
        input_tokens INTEGER,
        output_tokens INTEGER,
        total_tokens INTEGER,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (chat_id, seq)
    );

    CREATE TABLE IF NOT EXISTS spawns (
        chat_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        harness_id TEXT,
        first_seq INTEGER NOT NULL,
        last_seq INTEGER NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (chat_id, execution_id)
    );
    """

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def upsert(self, event: ChatEvent) -> None:
        with self._conn:
            self._upsert_event(event)
            self._upsert_spawn(event)
            self._upsert_turn(event)
            self._upsert_files(event)
            self._upsert_checkpoint(event)
            self._upsert_token_usage(event)

    def rebuild_from_log(self, event_log: ChatEventLog) -> None:
        with self._conn:
            for table in ("events", "files", "turns", "checkpoints", "token_usage", "spawns"):
                self._conn.execute(f"DELETE FROM {table}")
        for event in event_log.read_all():
            self.upsert(event)

    def close(self) -> None:
        self._conn.close()

    def _upsert_event(self, event: ChatEvent) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO events
            (chat_id, seq, type, execution_id, timestamp, turn_id,
             item_id, request_id, harness_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.chat_id,
                event.seq,
                event.type,
                event.execution_id,
                event.timestamp,
                event.turn_id,
                event.item_id,
                event.request_id,
                event.harness_id,
                _json(event.payload),
            ),
        )

    def _upsert_spawn(self, event: ChatEvent) -> None:
        if not event.execution_id:
            return
        self._conn.execute(
            """
            INSERT INTO spawns (chat_id, execution_id, harness_id, first_seq,
             last_seq, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, execution_id) DO UPDATE SET
                harness_id=COALESCE(excluded.harness_id, spawns.harness_id),
                last_seq=MAX(spawns.last_seq, excluded.last_seq),
                payload_json=excluded.payload_json
            """,
            (
                event.chat_id,
                event.execution_id,
                event.harness_id,
                event.seq,
                event.seq,
                _json(event.payload),
            ),
        )

    def _upsert_turn(self, event: ChatEvent) -> None:
        turn_id = event.turn_id or _payload_str(event.payload, "turn_id")
        if turn_id is None or event.type not in {"turn.started", "turn.completed"}:
            return
        if event.type == "turn.started":
            self._conn.execute(
                """
                INSERT INTO turns (chat_id, turn_id, execution_id, started_seq,
                 started_at, status, payload_json)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(chat_id, turn_id) DO UPDATE SET
                    started_seq=excluded.started_seq,
                    started_at=excluded.started_at,
                    status='active',
                    payload_json=excluded.payload_json
                """,
                (
                    event.chat_id,
                    turn_id,
                    event.execution_id,
                    event.seq,
                    event.timestamp,
                    _json(event.payload),
                ),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO turns (chat_id, turn_id, execution_id, completed_seq,
                 completed_at, status, payload_json)
                VALUES (?, ?, ?, ?, ?, 'completed', ?)
                ON CONFLICT(chat_id, turn_id) DO UPDATE SET
                    completed_seq=excluded.completed_seq,
                    completed_at=excluded.completed_at,
                    status='completed',
                    payload_json=excluded.payload_json
                """,
                (
                    event.chat_id,
                    turn_id,
                    event.execution_id,
                    event.seq,
                    event.timestamp,
                    _json(event.payload),
                ),
            )

    def _upsert_files(self, event: ChatEvent) -> None:
        if event.type != "files.persisted":
            return
        for file_payload in _payload_files(event.payload):
            path = file_payload.get("path")
            if not isinstance(path, str) or not path:
                continue
            action = file_payload.get("action")
            self._conn.execute(
                """
                INSERT OR REPLACE INTO files
                (chat_id, seq, path, action, turn_id, execution_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.chat_id,
                    event.seq,
                    path,
                    action if isinstance(action, str) else None,
                    event.turn_id,
                    event.execution_id,
                    _json(file_payload),
                ),
            )

    def _upsert_checkpoint(self, event: ChatEvent) -> None:
        if event.type not in {"checkpoint.created", "checkpoint.reverted"}:
            return
        commit_sha = _payload_str(event.payload, "commit_sha")
        turn_id = event.turn_id or _payload_str(event.payload, "turn_id")
        if commit_sha is None or turn_id is None:
            return
        if event.type == "checkpoint.created":
            self._conn.execute(
                """
                INSERT INTO checkpoints (chat_id, turn_id, commit_sha, created_seq,
                 created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, turn_id, commit_sha) DO UPDATE SET
                    created_seq=excluded.created_seq,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (
                    event.chat_id,
                    turn_id,
                    commit_sha,
                    event.seq,
                    event.timestamp,
                    _json(event.payload),
                ),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO checkpoints (chat_id, turn_id, commit_sha, reverted_seq,
                 reverted_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, turn_id, commit_sha) DO UPDATE SET
                    reverted_seq=excluded.reverted_seq,
                    reverted_at=excluded.reverted_at,
                    payload_json=excluded.payload_json
                """,
                (
                    event.chat_id,
                    turn_id,
                    commit_sha,
                    event.seq,
                    event.timestamp,
                    _json(event.payload),
                ),
            )

    def _upsert_token_usage(self, event: ChatEvent) -> None:
        usage = event.payload.get(
            "token_usage", event.payload if event.type == "token_usage" else None
        )
        if not isinstance(usage, dict):
            return
        typed_usage = cast("dict[str, object]", usage)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO token_usage
            (chat_id, seq, turn_id, execution_id, input_tokens,
             output_tokens, total_tokens, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.chat_id,
                event.seq,
                event.turn_id,
                event.execution_id,
                _optional_int(typed_usage.get("input_tokens")),
                _optional_int(typed_usage.get("output_tokens")),
                _optional_int(typed_usage.get("total_tokens")),
                _json(typed_usage),
            ),
        )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _payload_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _payload_files(payload: dict[str, Any]) -> list[dict[str, Any]]:
    files = payload.get("files", payload.get("paths"))
    if isinstance(files, list):
        result: list[dict[str, Any]] = []
        for item in cast("list[object]", files):
            if isinstance(item, dict):
                result.append(dict(cast("dict[str, Any]", item)))
            elif isinstance(item, str):
                result.append({"path": item})
        return result
    path = payload.get("path")
    if isinstance(path, str):
        return [payload]
    return []


__all__ = ["ChatEventIndex"]
