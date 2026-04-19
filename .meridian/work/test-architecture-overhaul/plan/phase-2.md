# Phase 2: Adapter Interfaces

## Objective
Create injectable adapter protocols for heartbeat and spawn repository with file-based implementations.

## Commits (Execute in Order)

### Commit 2.1: Create HeartbeatBackend Protocol
Create `src/meridian/lib/launch/streaming/heartbeat.py`:
```python
"""Heartbeat management with injectable backend."""
from pathlib import Path
from typing import Protocol

from meridian.lib.core.clock import Clock, RealClock

class HeartbeatBackend(Protocol):
    """Protocol for heartbeat touch operations."""
    def touch(self) -> None: ...
```

Update `streaming/__init__.py` to export.

Validation: Import works

### Commit 2.2: Create FileHeartbeat Implementation
Add to `heartbeat.py`:
```python
class FileHeartbeat:
    """File-based heartbeat implementation."""
    def __init__(self, path: Path, clock: Clock | None = None):
        self._path = path
        self._clock = clock or RealClock()
    
    def touch(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
```

Validation: Import works

### Commit 2.3: Add FakeHeartbeat to tests/support/fakes.py
Add to `tests/support/fakes.py`:
```python
class FakeHeartbeat:
    """Test double for HeartbeatBackend."""
    def __init__(self):
        self.touches: list[float] = []
        self._clock: FakeClock | None = None
    
    def set_clock(self, clock: FakeClock) -> None:
        self._clock = clock
    
    def touch(self) -> None:
        timestamp = self._clock.time() if self._clock else 0.0
        self.touches.append(timestamp)
```

Validation: Import works

### Commit 2.4: Create SpawnRepository Protocol
Create `src/meridian/lib/state/spawn/repository.py`:
```python
"""Spawn event persistence with injectable backend."""
from pathlib import Path
from typing import Protocol

from meridian.lib.core.clock import Clock, RealClock
from meridian.lib.core.types import SpawnId
from .events import SpawnEvent

class SpawnRepository(Protocol):
    """Protocol for spawn event persistence."""
    def append_event(self, event: SpawnEvent) -> None: ...
    def read_events(self) -> list[SpawnEvent]: ...
    def next_id(self) -> SpawnId: ...
```

Validation: Import works

### Commit 2.5: Create FileSpawnRepository Implementation
Add to `repository.py`:
```python
from meridian.lib.state.paths import StateRootPaths
from meridian.lib.state.event_store import append_event as _append_event, read_events as _read_events, lock_file

class FileSpawnRepository:
    """File-based spawn repository implementation."""
    def __init__(self, paths: StateRootPaths, clock: Clock | None = None):
        self._paths = paths
        self._clock = clock or RealClock()
    
    def append_event(self, event: SpawnEvent) -> None:
        _append_event(
            self._paths.spawns_jsonl,
            self._paths.spawns_flock,
            event,
            exclude_none=True,
        )
    
    def read_events(self) -> list[SpawnEvent]:
        from .events import parse_event
        return _read_events(self._paths.spawns_jsonl, parse_event)
    
    def next_id(self) -> SpawnId:
        # Count start events
        events = self.read_events()
        starts = sum(1 for e in events if e.event == "start")
        return SpawnId(f"p{starts + 1}")
```

Note: May need to adjust imports based on actual code structure.

Validation: Import works

### Commit 2.6: Add FakeSpawnRepository to tests/support/fakes.py
Add to `tests/support/fakes.py`:
```python
from meridian.lib.core.types import SpawnId

class FakeSpawnRepository:
    """In-memory spawn repository for testing."""
    def __init__(self):
        self._events: list = []
        self._next_id_counter = 1
    
    def append_event(self, event) -> None:
        self._events.append(event)
    
    def read_events(self) -> list:
        return list(self._events)
    
    def next_id(self) -> SpawnId:
        id = SpawnId(f"p{self._next_id_counter}")
        self._next_id_counter += 1
        return id
```

Validation: Import works

## Exit Criteria
- All 6 commits made atomically
- Each commit passes pytest
- Protocols importable from expected locations
- Fakes available in tests/support/fakes.py
