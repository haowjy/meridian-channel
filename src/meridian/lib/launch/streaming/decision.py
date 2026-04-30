"""Pure terminal event classification logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from meridian.lib.harness.semantics import TerminalEventOutcome, terminal_outcome

if TYPE_CHECKING:
    from meridian.lib.harness.connections.base import HarnessEvent


def terminal_event_outcome(event: HarnessEvent) -> TerminalEventOutcome | None:
    """Return terminal drain-policy outcome for a harness event."""

    return terminal_outcome(event)


__all__ = [
    "TerminalEventOutcome",
    "terminal_event_outcome",
]
