"""Pure terminal event classification logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from meridian.lib.core.domain import SpawnStatus

if TYPE_CHECKING:
    from meridian.lib.harness.connections.base import HarnessEvent


@dataclass(frozen=True)
class TerminalEventOutcome:
    status: SpawnStatus
    exit_code: int
    error: str | None = None


def _stringify_terminal_error(error: object) -> str | None:
    if error is None:
        return None
    if isinstance(error, str):
        normalized = error.strip()
        return normalized or None
    try:
        rendered = json.dumps(error, sort_keys=True)
    except (TypeError, ValueError):
        rendered = str(error)
    normalized = rendered.strip()
    return normalized or None


def terminal_event_outcome(event: HarnessEvent) -> TerminalEventOutcome | None:
    _ = event
    return None


__all__ = [
    "TerminalEventOutcome",
    "terminal_event_outcome",
]
