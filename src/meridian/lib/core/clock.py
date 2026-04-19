"""Shared time abstraction for dependency injection."""

from datetime import datetime, timezone
import time
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...
    def time(self) -> float: ...
    def utc_now_iso(self) -> str: ...


class RealClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def time(self) -> float:
        return time.time()

    def utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
