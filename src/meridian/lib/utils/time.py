"""Time unit conversion helpers."""

from __future__ import annotations


def minutes_to_seconds(timeout_minutes: float | None) -> float | None:
    """Convert an optional minutes value to seconds."""

    if timeout_minutes is None:
        return None
    return timeout_minutes * 60.0
