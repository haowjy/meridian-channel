"""JSONL compatibility layer for dual-write and import."""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import cast

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
type JSONRow = dict[str, JSONValue]


@contextmanager
def index_lock(lock_path: Path, *, exclusive: bool):
    """Lock the shared runs lock file with flock."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(handle.fileno(), mode)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_jsonl_row(path: Path, row: JSONRow) -> None:
    """Append one JSON object line without acquiring locks."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{payload}\n")


def read_jsonl_rows(path: Path) -> list[JSONRow]:
    """Read JSON objects from a JSONL file, skipping malformed rows."""

    if not path.exists():
        return []

    rows: list[JSONRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(cast("JSONRow", payload))
    return rows
