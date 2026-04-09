"""Contracts for mapping harness events into AG-UI events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from meridian.lib.harness.connections.base import HarnessEvent

if TYPE_CHECKING:
    from ag_ui.core import BaseEvent, RunFinishedEvent, RunStartedEvent


class AGUIMapper(Protocol):
    """Translate harness-native events into AG-UI protocol events."""

    def translate(self, event: HarnessEvent) -> list[BaseEvent]: ...

    def make_run_started(self, spawn_id: str) -> RunStartedEvent: ...

    def make_run_finished(self, spawn_id: str) -> RunFinishedEvent: ...


__all__ = ["AGUIMapper"]
