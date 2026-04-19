"""Heartbeat management with injectable backends."""

from __future__ import annotations

from typing import Protocol


class HeartbeatBackend(Protocol):
    """Protocol for heartbeat touch operations."""

    def touch(self) -> None: ...


__all__ = ["HeartbeatBackend"]
