"""Serialization helpers shared across process boundaries."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast


def to_jsonable(value: Any) -> Any:
    """Convert supported values to JSON-serializable payloads."""

    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        typed_dict = cast("dict[object, object]", value)
        return {str(key): to_jsonable(item) for key, item in typed_dict.items()}
    if isinstance(value, (list, tuple, set)):
        typed_seq = cast("list[object] | tuple[object, ...] | set[object]", value)
        return [to_jsonable(item) for item in typed_seq]
    return value
