# Spawn Store — Technical Architecture

## Current State

`spawn_store.py` is 737 lines containing:
- Event model definitions (SpawnStartEvent, SpawnUpdateEvent, etc.)
- `_record_from_events()` — Pure event reducer (most valuable logic)
- ID generation (`next_spawn_id`)
- Direct file I/O via `append_event()`, `read_events()`, `lock_file()`
- Public API functions (`start_spawn`, `update_spawn`, `finalize_spawn`, etc.)

The event reducer `_record_from_events()` is pure but private. Tests use real filesystem.

---

## Target State

```
src/meridian/lib/state/spawn/
├── __init__.py          # Re-exports for public API
├── adapters.py          # FileAdapter, LockAdapter protocols
├── events.py            # Event models + pure reducer (public)
├── repository.py        # File I/O layer
└── store.py             # Composition layer (public API)
```

---

## File Details

### events.py

```python
"""Spawn event models and pure reducer logic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from meridian.lib.core.domain import SpawnStatus
from meridian.lib.core.spawn_lifecycle import (
    TERMINAL_SPAWN_STATUSES,
    is_active_spawn_status,
    validate_transition,
)

# ── Event Models ────────────────────────────────────────────────────────────

LaunchMode = Literal["background", "foreground", "app"]
SpawnOrigin = Literal["runner", "launcher", "launch_failure", "cancel", "reconciler"]
AUTHORITATIVE_ORIGINS: frozenset[SpawnOrigin] = frozenset((
    "runner", "launcher", "launch_failure", "cancel",
))


class SpawnRecord(BaseModel):
    """Derived spawn state assembled from spawn JSONL events."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    chat_id: str | None
    parent_id: str | None
    # ... (existing fields)


class SpawnStartEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    v: int = 1
    event: Literal["start"] = "start"
    # ... (existing fields)


class SpawnUpdateEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    v: int = 1
    event: Literal["update"] = "update"
    # ... (existing fields)


class SpawnExitedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    v: int = 1
    event: Literal["exited"] = "exited"
    # ... (existing fields)


class SpawnFinalizeEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    v: int = 1
    event: Literal["finalize"] = "finalize"
    # ... (existing fields)


type SpawnEvent = SpawnStartEvent | SpawnUpdateEvent | SpawnExitedEvent | SpawnFinalizeEvent


# ── Pure Reducer ────────────────────────────────────────────────────────────


def _empty_record(spawn_id: str) -> SpawnRecord:
    """Create empty record for ID."""
    return SpawnRecord(
        id=spawn_id,
        chat_id=None,
        # ... (existing initialization)
    )


def reduce_events(events: list[SpawnEvent]) -> dict[str, SpawnRecord]:
    """Reduce event list to spawn records.
    
    Pure function: operates only on in-memory event list.
    No I/O, no filesystem access, no side effects.
    
    This is the core projection logic for spawn state.
    Tests call this directly with constructed event lists.
    """
    records: dict[str, SpawnRecord] = {}
    
    for event in events:
        spawn_id = event.id
        if not spawn_id:
            continue
        
        current = records.get(spawn_id, _empty_record(spawn_id))
        
        if isinstance(event, SpawnStartEvent):
            records[spawn_id] = current.model_copy(update={
                "chat_id": event.chat_id if event.chat_id is not None else current.chat_id,
                # ... (existing field merging)
            })
            continue
        
        if isinstance(event, SpawnUpdateEvent):
            # ... (existing update logic)
            continue
        
        if isinstance(event, SpawnExitedEvent):
            # ... (existing exited logic)
            continue
        
        # SpawnFinalizeEvent
        # ... (existing finalize logic with origin precedence)
    
    return records


def parse_event(payload: dict[str, Any]) -> SpawnEvent | None:
    """Parse JSON payload into typed event.
    
    Returns None for unrecognized or invalid events.
    """
    event_type = payload.get("event")
    try:
        if event_type == "start":
            return SpawnStartEvent.model_validate(payload)
        if event_type == "update":
            return SpawnUpdateEvent.model_validate(payload)
        if event_type == "exited":
            return SpawnExitedEvent.model_validate(payload)
        if event_type == "finalize":
            return SpawnFinalizeEvent.model_validate(payload)
    except Exception:
        return None
    return None
```

### adapters.py

```python
"""Protocol definitions for spawn store dependencies."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

from meridian.lib.core.clock import Clock  # Shared clock protocol


class FileAdapter(Protocol):
    """Injectable file operations for JSONL read/write."""
    
    def read_lines(self, path: Path) -> list[str]:
        """Read all lines from file. Return empty list if missing."""
        ...
    
    def append_line(self, path: Path, line: str) -> None:
        """Append line to file, creating if needed."""
        ...
    
    def exists(self, path: Path) -> bool:
        """Return True if file exists."""
        ...


class LockAdapter(Protocol):
    """Injectable file locking for concurrent access."""
    
    @contextmanager
    def lock(self, path: Path) -> Iterator[None]:
        """Acquire exclusive lock on file, releasing on exit."""
        ...


# ── Production Implementations ──────────────────────────────────────────────


class RealFileAdapter:
    """Production file adapter using real filesystem."""
    
    def read_lines(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()
    
    def append_line(self, path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
    
    def exists(self, path: Path) -> bool:
        return path.exists()


class RealLockAdapter:
    """Production lock adapter using flock."""
    
    @contextmanager
    def lock(self, path: Path) -> Iterator[None]:
        from meridian.lib.state.event_store import lock_file
        with lock_file(path):
            yield
```

### repository.py

```python
"""File I/O layer for spawn events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.core.clock import Clock
    from .adapters import FileAdapter, LockAdapter
    from .events import SpawnEvent


class SpawnRepository:
    """Handles reading and writing spawn events to JSONL."""
    
    def __init__(
        self,
        *,
        file_adapter: FileAdapter,
        lock_adapter: LockAdapter,
        clock: Clock,
    ) -> None:
        self._file = file_adapter
        self._lock = lock_adapter
        self._clock = clock
    
    def read_events(self, path: Path) -> list[SpawnEvent]:
        """Read and parse all events from JSONL file."""
        from .events import parse_event
        
        events = []
        for line in self._file.read_lines(path):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = parse_event(payload)
            if event is not None:
                events.append(event)
        return events
    
    def append_event(
        self,
        path: Path,
        lock_path: Path,
        event: SpawnEvent,
        exclude_none: bool = True,
    ) -> None:
        """Append event to JSONL file under lock."""
        payload = event.model_dump(mode="json")
        if exclude_none:
            payload = {k: v for k, v in payload.items() if v is not None}
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        
        with self._lock.lock(lock_path):
            self._file.append_line(path, line)
    
    def count_start_events(self, path: Path) -> int:
        """Count start events for ID generation."""
        events = self.read_events(path)
        return sum(1 for e in events if hasattr(e, "event") and e.event == "start")
```

### store.py

```python
"""Spawn store public API composing events and repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from meridian.lib.core.types import SpawnId

from .adapters import (
    Clock,
    FileAdapter,
    LockAdapter,
    RealFileAdapter,
    RealLockAdapter,
)
from .events import (
    LaunchMode,
    SpawnEvent,
    SpawnFinalizeEvent,
    SpawnOrigin,
    SpawnRecord,
    SpawnStartEvent,
    SpawnUpdateEvent,
    SpawnExitedEvent,
    reduce_events,
    AUTHORITATIVE_ORIGINS,
)
from .repository import SpawnRepository
from meridian.lib.core.clock import RealClock
from meridian.lib.state.paths import StateRootPaths


def _get_default_repository(state_root: Path) -> SpawnRepository:
    """Create repository with production dependencies."""
    return SpawnRepository(
        file_adapter=RealFileAdapter(),
        lock_adapter=RealLockAdapter(),
        clock=RealClock(),
    )


def next_spawn_id(
    state_root: Path,
    *,
    repository: SpawnRepository | None = None,
) -> SpawnId:
    """Return next spawn ID (p1, p2, ...)."""
    repo = repository or _get_default_repository(state_root)
    paths = StateRootPaths.from_root_dir(state_root)
    starts = repo.count_start_events(paths.spawns_jsonl)
    return SpawnId(f"p{starts + 1}")


def start_spawn(
    state_root: Path,
    *,
    chat_id: str,
    model: str,
    agent: str,
    harness: str,
    prompt: str,
    # ... other params
    repository: SpawnRepository | None = None,
    clock: Clock | None = None,
) -> SpawnId:
    """Append spawn start event and return spawn ID."""
    repo = repository or _get_default_repository(state_root)
    clock = clock or RealClock()
    paths = StateRootPaths.from_root_dir(state_root)
    
    # ... (existing logic, using repo.append_event)
    pass


def update_spawn(
    state_root: Path,
    spawn_id: SpawnId | str,
    *,
    repository: SpawnRepository | None = None,
    **kwargs,
) -> None:
    """Append metadata update event."""
    repo = repository or _get_default_repository(state_root)
    paths = StateRootPaths.from_root_dir(state_root)
    
    event = SpawnUpdateEvent(id=str(spawn_id), **kwargs)
    repo.append_event(paths.spawns_jsonl, paths.spawns_flock, event)


def finalize_spawn(
    state_root: Path,
    spawn_id: SpawnId | str,
    status: str,
    exit_code: int,
    *,
    origin: SpawnOrigin,
    repository: SpawnRepository | None = None,
    **kwargs,
) -> bool:
    """Append finalize event and return whether this writer set terminal status."""
    repo = repository or _get_default_repository(state_root)
    paths = StateRootPaths.from_root_dir(state_root)
    
    with repo._lock.lock(paths.spawns_flock):
        events = repo.read_events(paths.spawns_jsonl)
        records = reduce_events(events)
        record = records.get(str(spawn_id))
        
        # ... (existing terminal transition logic)
        
        event = SpawnFinalizeEvent(
            id=str(spawn_id),
            status=status,
            exit_code=exit_code,
            origin=origin,
            **kwargs,
        )
        repo.append_event(paths.spawns_jsonl, paths.spawns_flock, event)
        
        return was_active


def list_spawns(
    state_root: Path,
    filters: Mapping[str, Any] | None = None,
    *,
    repository: SpawnRepository | None = None,
) -> list[SpawnRecord]:
    """List derived spawn records with optional filters."""
    repo = repository or _get_default_repository(state_root)
    paths = StateRootPaths.from_root_dir(state_root)
    
    events = repo.read_events(paths.spawns_jsonl)
    spawns = list(reduce_events(events).values())
    
    # ... (existing filter logic)
    return sorted(spawns, key=_spawn_sort_key)


def get_spawn(
    state_root: Path,
    spawn_id: SpawnId | str,
    *,
    repository: SpawnRepository | None = None,
) -> SpawnRecord | None:
    """Return one spawn by ID."""
    spawns = list_spawns(state_root, repository=repository)
    wanted = str(spawn_id)
    for spawn in spawns:
        if spawn.id == wanted:
            return spawn
    return None
```

---

## Test Migration

### Before (real filesystem always)
```python
def test_spawn_finalize_precedence(tmp_path):
    state_root = tmp_path / ".meridian"
    state_root.mkdir()
    
    spawn_id = start_spawn(state_root, ...)
    finalize_spawn(state_root, spawn_id, status="failed", origin="reconciler", ...)
    finalize_spawn(state_root, spawn_id, status="succeeded", origin="runner", ...)
    
    spawn = get_spawn(state_root, spawn_id)
    assert spawn.status == "succeeded"  # runner wins over reconciler
```

### After (unit tests use pure reducer)
```python
from meridian.lib.state.spawn.events import (
    reduce_events,
    SpawnStartEvent,
    SpawnFinalizeEvent,
)

def test_finalize_origin_precedence():
    """Unit test: pure reducer logic, no filesystem."""
    events = [
        SpawnStartEvent(id="p1", chat_id="c1", model="m", agent="a", harness="h", prompt="p"),
        SpawnFinalizeEvent(id="p1", status="failed", exit_code=1, origin="reconciler"),
        SpawnFinalizeEvent(id="p1", status="succeeded", exit_code=0, origin="runner"),
    ]
    
    records = reduce_events(events)
    assert records["p1"].status == "succeeded"  # runner wins
    assert records["p1"].terminal_origin == "runner"


def test_spawn_store_integration(tmp_path):
    """Integration test: real filesystem."""
    state_root = tmp_path / ".meridian"
    state_root.mkdir()
    
    spawn_id = start_spawn(state_root, ...)
    assert get_spawn(state_root, spawn_id) is not None
```

---

## Key Benefits

1. **Pure reducer is testable without filesystem** — 80% of spawn_store.py logic can now be unit tested

2. **FileAdapter enables memory tests** — Integration tests that need concurrent access can use fake file adapter

3. **Clock injection** — Deterministic timestamp testing

4. **Backward compatible** — Original `spawn_store` module becomes thin re-export
