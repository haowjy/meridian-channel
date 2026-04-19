"""Spawn event persistence with injectable backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from meridian.lib.core.types import SpawnId

if TYPE_CHECKING:
    from meridian.lib.state.spawn_store import SpawnEvent


class SpawnRepository(Protocol):
    """Protocol for spawn event persistence."""

    def append_event(self, event: SpawnEvent) -> None: ...

    def read_events(self) -> list[SpawnEvent]: ...

    def next_id(self) -> SpawnId: ...


__all__ = ["SpawnRepository"]
