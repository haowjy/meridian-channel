# Spawn Store — Behavioral Specification

## Module Responsibilities After Split

The current `spawn_store.py` (737 lines) mixes:
- Event model definitions (SpawnStartEvent, SpawnUpdateEvent, etc.)
- Event reducer logic (_record_from_events — pure projection)
- File I/O operations (read_events, append_event, lock_file)
- ID generation (next_spawn_id counting start events)
- Time generation (utc_now_iso for timestamps)

After splitting, each file has ONE responsibility.

---

## state/spawn/events.py — Pure Event Reducer

**[SPEC-SS-EVT-001]** WHEN `reduce_events(events: list[SpawnEvent])` is called, it SHALL return `dict[str, SpawnRecord]` by folding events in order.

**[SPEC-SS-EVT-002]** The reducer SHALL handle:
- `SpawnStartEvent` — Initialize record with spawn metadata
- `SpawnUpdateEvent` — Merge non-None fields, respect terminal status freeze
- `SpawnExitedEvent` — Record process exit code and timestamp
- `SpawnFinalizeEvent` — Set terminal status with origin precedence

**[SPEC-SS-EVT-003]** WHEN multiple finalize events exist, the reducer SHALL:
- Preserve first authoritative terminal status (runner, launcher, launch_failure, cancel)
- Allow authoritative origins to override reconciler status
- Always merge duration, cost, and token counts

**[SPEC-SS-EVT-004]** The events module SHALL NOT import os, pathlib, or any I/O modules — it operates on pure data only.

**[SPEC-SS-EVT-005]** WHEN tests verify state projection, they SHALL construct event lists in-memory and call `reduce_events()` directly.

---

## state/spawn/repository.py — File I/O Adapter

**[SPEC-SS-REP-001]** WHEN `SpawnRepository` is constructed, it SHALL accept:
- `file_adapter: FileAdapter` — Injectable file operations
- `clock: Clock` — Injectable time source
- `lock_adapter: LockAdapter` — Injectable file locking

**[SPEC-SS-REP-002]** WHEN `append_event()` is called, it SHALL:
- Acquire lock via lock_adapter
- Serialize event to JSON line
- Append via file_adapter
- Release lock

**[SPEC-SS-REP-003]** WHEN `read_events()` is called, it SHALL:
- Read lines via file_adapter
- Parse each line, skipping invalid JSON
- Return list of parsed events

**[SPEC-SS-REP-004]** WHEN tests verify file operations, they SHALL inject `MemoryFileAdapter` that stores lines in a list.

---

## state/spawn/store.py — Composition Layer

**[SPEC-SS-STR-001]** WHEN `start_spawn()` is called, it SHALL:
- Generate spawn ID via ID adapter (if not provided)
- Create start event with clock-provided timestamp
- Append via repository
- Return spawn ID

**[SPEC-SS-STR-002]** WHEN `finalize_spawn()` is called, it SHALL:
- Read current state via repository
- Validate transition via events module
- Append finalize event
- Return whether this writer set terminal status

**[SPEC-SS-STR-003]** The store module SHALL be the public API — events.py and repository.py are internal.

**[SPEC-SS-STR-004]** WHEN the store is used in production, it SHALL be constructed with real file/lock/clock adapters at composition root.

---

## Adapter Protocols

**[SPEC-SS-ADP-001]** The `FileAdapter` protocol SHALL define:
```python
class FileAdapter(Protocol):
    def read_lines(self, path: Path) -> list[str]: ...
    def append_line(self, path: Path, line: str) -> None: ...
    def exists(self, path: Path) -> bool: ...
```

**[SPEC-SS-ADP-002]** The `LockAdapter` protocol SHALL define:
```python
class LockAdapter(Protocol):
    @contextmanager
    def lock(self, path: Path) -> Iterator[None]: ...
```

**[SPEC-SS-ADP-003]** The `IdGenerator` protocol SHALL define:
```python
class IdGenerator(Protocol):
    def next_spawn_id(self) -> SpawnId: ...
```

---

## Runtime Value Justification

1. **Pure event reducer** — Enables offline replay of spawn history for debugging, future migration tooling.

2. **FileAdapter** — Prepares for future SQLite or remote storage backends without changing business logic.

3. **LockAdapter** — Enables testing of concurrent access patterns without real file locks.

4. **Clock injection** — Enables deterministic testing and future distributed clock support.
