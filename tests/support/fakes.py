"""Test doubles for deterministic behavior in unit and integration tests."""

from datetime import datetime, timezone


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def time(self) -> float:
        return self._now

    def utc_now_iso(self) -> str:
        return datetime.fromtimestamp(self._now, tz=timezone.utc).isoformat()

    def advance(self, seconds: float) -> None:
        self._now += seconds
