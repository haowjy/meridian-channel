"""Append-only JSONL source of truth for normalized chat events."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from meridian.lib.chat.protocol import ChatEvent
from meridian.lib.state.atomic import append_text_line

logger = logging.getLogger(__name__)


class ChatEventLog:
    """Append-only JSONL event log with monotonic per-chat sequence numbers."""

    def __init__(self, log_path: Path) -> None:
        self._path = log_path
        self._seq, self._append_offset = self._recover_seq_and_offset()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def next_seq(self) -> int:
        return self._seq

    def _recover_seq_and_offset(self) -> tuple[int, int]:
        if not self._path.exists():
            return 0, 0
        count = 0
        last_good_offset = 0
        with self._path.open("rb") as handle:
            while True:
                line_start = handle.tell()
                raw_line = handle.readline()
                if raw_line == b"":
                    break
                line = raw_line.strip()
                if not line:
                    last_good_offset = handle.tell()
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(
                        "Ignoring truncated chat event log line during seq recovery: %s",
                        self._path,
                    )
                    return count, line_start
                count += 1
                last_good_offset = handle.tell()
        return count, last_good_offset

    def append(self, event: ChatEvent) -> ChatEvent:
        """Assign the next seq, append to disk, and return the persisted event."""

        self._truncate_recovered_tail()
        persisted = replace(event, seq=self._seq)
        line = json.dumps(asdict(persisted), separators=(",", ":"), sort_keys=True) + "\n"
        append_text_line(self._path, line)
        self._seq += 1
        self._append_offset = self._path.stat().st_size
        return persisted

    def read_from(self, start_seq: int) -> Iterator[ChatEvent]:
        """Yield complete events with seq >= start_seq."""

        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError:
                    logger.warning("Stopping chat event replay at truncated line: %s", self._path)
                    break
                event = _event_from_mapping(data)
                if event.seq >= start_seq:
                    yield event

    def read_all(self) -> Iterator[ChatEvent]:
        """Yield all complete events in the log."""

        yield from self.read_from(0)

    def _truncate_recovered_tail(self) -> None:
        if not self._path.exists():
            return
        size = self._path.stat().st_size
        if size <= self._append_offset:
            return
        with self._path.open("r+b") as handle:
            handle.truncate(self._append_offset)


def _event_from_mapping(data: dict[str, Any]) -> ChatEvent:
    return ChatEvent(
        type=str(data["type"]),
        seq=int(data["seq"]),
        chat_id=str(data["chat_id"]),
        execution_id=str(data["execution_id"]),
        timestamp=str(data["timestamp"]),
        turn_id=data.get("turn_id"),
        item_id=data.get("item_id"),
        request_id=data.get("request_id"),
        payload=dict(data.get("payload") or {}),
        harness_id=data.get("harness_id"),
    )


__all__ = ["ChatEventLog"]
