# Refactor Agenda

This document lists structural rearrangements that must be sequenced early because they unlock safe parallel implementation of the test architecture overhaul.

## Priority Legend

- **🔴 P0** — Blocks multiple phases; do first
- **🟡 P1** — Blocks one phase or improves parallelization
- **🟢 P2** — Cleanup; can be done anytime after P0/P1

---

## [REF-001] Extract Shared Clock Protocol

**Priority:** 🔴 P0  
**Blocks:** All injectable adapter work (streaming_runner, process, spawn_store)

### Current State
No shared Clock protocol exists. Each module calls `time.time()`, `time.monotonic()`, or `utc_now_iso()` directly.

### Target State
Single `Clock` protocol in `lib/core/clock.py` with:
- `monotonic() -> float`
- `time() -> float`  
- `utc_now_iso() -> str`

Production `RealClock` implementation in same file.

### Why First
Every injectable adapter design references Clock. Without shared definition, each module would define its own, creating drift. Shared protocol enables consistent `FakeClock` in tests.

### Files Touched
- **Create:** `src/meridian/lib/core/clock.py`
- **Modify:** None (imports added later during module splits)

### Estimated Size
~50 lines

---

## [REF-002] Create tests/support/ Directory Structure

**Priority:** 🔴 P0  
**Blocks:** All test migration and fixture work

### Current State
No `tests/support/` directory. Test helpers scattered in conftest.py files or inline in test files.

### Target State
```
tests/support/
├── __init__.py
├── fakes.py          # FakeClock, FakeFileAdapter, etc.
├── fixtures.py       # Factory fixtures
└── assertions.py     # Custom assertion helpers (initially empty)
```

### Why First
Test migration phases reference `tests/support/` imports. Creating empty structure with `__init__.py` allows parallel work on fake implementations and fixture factories.

### Files Touched
- **Create:** `tests/support/__init__.py`, `tests/support/fakes.py`, `tests/support/fixtures.py`, `tests/support/assertions.py`
- **Modify:** None

### Estimated Size
~20 lines (stubs only; content added in later phases)

---

## [REF-003] Add Marker Registration to Root conftest.py

**Priority:** 🔴 P0  
**Blocks:** All test classification and CI configuration

### Current State
Root `conftest.py` has `posix_only` and `windows_only` only. No `unit`, `integration`, `slow`, etc.

### Target State
Add marker registration for: `unit`, `integration`, `e2e`, `contract`, `slow`

### Why First
Marker-based test selection (`pytest -m unit`) requires markers to be registered. CI configuration references these markers.

### Files Touched
- **Modify:** `tests/conftest.py`

### Estimated Size
~10 lines added

---

## [REF-004] Extract Pure Event Reducer from spawn_store.py

**Priority:** 🟡 P1  
**Blocks:** spawn_store unit tests without filesystem

### Current State
`_record_from_events()` is private function in `spawn_store.py`. Tests must use real filesystem to verify event projection logic.

### Target State
Public `reduce_events()` in `state/spawn/events.py`. Pure function operating on `list[SpawnEvent]` with no I/O.

### Why First
Event projection is the most valuable pure logic in spawn_store.py. Extracting it first enables:
- Unit tests for projection logic (80% of spawn_store complexity)
- Foundation for repository/store split

### Files Touched
- **Create:** `src/meridian/lib/state/spawn/__init__.py`, `src/meridian/lib/state/spawn/events.py`
- **Modify:** `src/meridian/lib/state/spawn_store.py` (re-export from new location)

### Estimated Size
~250 lines (mostly moved, some signature changes)

### Migration Note
Original `spawn_store.py` becomes thin re-export layer. All existing imports continue working.

---

## [REF-005] Extract terminal_event_outcome() from streaming_runner.py

**Priority:** 🟡 P1  
**Blocks:** streaming_runner unit tests for terminal classification

### Current State
`terminal_event_outcome()` is in `streaming_runner.py` alongside async orchestration code.

### Target State
Public function in `launch/streaming/decision.py`. Pure function operating on `HarnessEvent` with no I/O.

### Why First
Terminal event classification is pure decision logic mixed with async I/O code. Extracting it:
- Enables unit tests for harness-specific terminal patterns
- Establishes decision.py as home for retry logic (also pure)

### Files Touched
- **Create:** `src/meridian/lib/launch/streaming/__init__.py`, `src/meridian/lib/launch/streaming/decision.py`
- **Modify:** `src/meridian/lib/launch/streaming_runner.py` (re-export)

### Estimated Size
~100 lines (mostly moved)

---

## [REF-006] Create Test Directory Skeleton

**Priority:** 🟡 P1  
**Blocks:** Parallel test migration phases

### Current State
Flat test structure with ad-hoc subdirectories (`tests/harness/`, `tests/exec/`, etc.)

### Target State
```
tests/
├── unit/
│   ├── conftest.py      # Auto-marker hook
│   ├── state/
│   ├── launch/
│   └── harness/
├── integration/
│   ├── conftest.py      # Auto-marker hook
│   ├── state/
│   ├── launch/
│   └── cli/
├── contract/
│   └── conftest.py
├── platform/
│   ├── posix/conftest.py
│   └── windows/conftest.py
└── e2e/
    └── conftest.py
```

### Why First
Directory structure with conftest.py hooks must exist before tests can be moved. Auto-marker hooks depend on path patterns.

### Files Touched
- **Create:** Directory structure and conftest.py files (auto-marker hooks)
- **Modify:** None

### Estimated Size
~100 lines across conftest.py files

---

## [REF-007] Rename existing test directories to legacy_

**Priority:** 🟢 P2  
**Blocks:** Nothing; cleanup for clarity

### Current State
Mix of old and new test directories creates confusion during migration.

### Target State
Prefix old directories with `legacy_` during migration (e.g., `tests/legacy_exec/`). Remove prefix after migration complete.

### Why Defer
Not blocking anything. Can be done during or after test migration for organizational clarity.

### Alternative
Skip renaming; move tests directly. Renaming is optional organizational aid.

---

## [REF-008] Update pytest.ini Configuration

**Priority:** 🟢 P2  
**Blocks:** CI configuration only

### Current State
`pytest.ini` or `pyproject.toml` pytest section may not have:
- `strict-markers = true`
- Updated test paths
- Timeout defaults

### Target State
```ini
[pytest]
strict-markers = true
testpaths = tests
markers =
    unit: pure logic tests
    integration: one real boundary
    # ... etc
timeout = 60
```

### Why Defer
Not blocking implementation. Can be added when CI is configured.

---

## Sequencing Diagram

```
Week 1: Foundation (P0)
├── REF-001: Clock protocol
├── REF-002: tests/support/ structure
└── REF-003: Marker registration

Week 2: Pure Logic Extraction (P1)
├── REF-004: Event reducer extraction
├── REF-005: terminal_event_outcome extraction
└── REF-006: Test directory skeleton

Week 3+: Migration and Cleanup (P2)
├── REF-007: Legacy directory naming (optional)
└── REF-008: pytest.ini updates
```

---

## Validation Criteria

After P0 refactors:
- [ ] `from meridian.lib.core.clock import Clock, RealClock` works
- [ ] `from tests.support.fakes import FakeClock` works
- [ ] `pytest --collect-only -m unit` returns 0 (marker recognized)

After P1 refactors:
- [ ] `from meridian.lib.state.spawn.events import reduce_events` works
- [ ] `from meridian.lib.launch.streaming.decision import terminal_event_outcome` works
- [ ] `tests/unit/conftest.py` exists with auto-marker hook
- [ ] All existing tests still pass (backward compatibility)

After P2 refactors:
- [ ] `pytest -m unit` runs cleanly
- [ ] `pytest -m integration` runs cleanly
- [ ] CI config updated with marker-based selection
