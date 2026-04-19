# Test Architecture Overhaul — Technical Architecture

## Overview

This architecture realizes the behavioral specification through two parallel tracks:

1. **Production code restructuring** — Split monolithic modules into single-purpose files with injectable dependencies
2. **Test infrastructure** — Establish directory conventions, fixture layer, and CI configuration

---

## Module Dependency Graph (After Refactoring)

```
                                    ┌─────────────────────────────┐
                                    │   Composition Root (CLI)    │
                                    │   - Creates real adapters   │
                                    │   - Wires dependencies      │
                                    └──────────────┬──────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    │                              │                              │
                    ▼                              ▼                              ▼
    ┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
    │   launch/streaming/       │  │   launch/process/         │  │   state/spawn/            │
    │   runner.py (shell)       │  │   runner.py (shell)       │  │   store.py (facade)       │
    │                           │  │                           │  │                           │
    │   Composes:               │  │   Composes:               │  │   Composes:               │
    │   - decision.py           │  │   - session.py            │  │   - repository.py         │
    │   - heartbeat.py          │  │   - pty_launcher.py       │  │   - events.py             │
    │   - adapters.py           │  │   - ports.py              │  │   - adapters.py           │
    └───────────────────────────┘  └───────────────────────────┘  └───────────────────────────┘
                    │                              │                              │
                    │                              │                              │
                    ▼                              ▼                              ▼
    ┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
    │   Shared Ports            │  │   Shared Ports            │  │   Shared Ports            │
    │   - Clock                 │  │   - Clock                 │  │   - Clock                 │
    │   - SpawnStoreAdapter     │  │   - SpawnStoreAdapter     │  │   - FileAdapter           │
    │   - HeartbeatAdapter      │  │   - ProcessLauncher       │  │   - LockAdapter           │
    │   - SignalCoordinator     │  │                           │  │                           │
    └───────────────────────────┘  └───────────────────────────┘  └───────────────────────────┘
```

---

## Test Directory Structure

```
tests/
├── conftest.py                    # Root: env isolation, marker registration, auto-markers
├── pytest.ini                     # Strict markers, test paths
│
├── unit/                          # Pure logic, no I/O
│   ├── conftest.py                # Auto-applies @pytest.mark.unit
│   ├── state/
│   │   ├── test_spawn_events.py   # Tests reduce_events() with in-memory events
│   │   └── test_session_events.py
│   ├── launch/
│   │   ├── test_retry_decision.py # Tests should_retry(), classify_error()
│   │   └── test_terminal_events.py# Tests terminal_event_outcome()
│   └── harness/
│       └── test_event_parsing.py  # Tests harness event parsing
│
├── integration/                   # One real boundary
│   ├── conftest.py                # Auto-applies @pytest.mark.integration
│   ├── state/
│   │   ├── test_spawn_store.py    # Real filesystem, isolated tmp_path
│   │   └── test_artifact_store.py
│   ├── launch/
│   │   └── test_process_launch.py # Real subprocess, controlled test binaries
│   └── cli/
│       └── test_cli_spawn.py      # Real CLI, isolated state root
│
├── contract/
│   ├── conftest.py
│   ├── test_clock_protocol.py     # Verifies all Clock impls match protocol
│   ├── test_file_adapter.py       # Verifies all FileAdapter impls
│   └── harness/
│       └── test_launch_spec.py    # Verifies launch spec → harness parity
│
├── platform/
│   ├── posix/
│   │   ├── conftest.py            # Auto-applies @pytest.mark.posix_only
│   │   ├── test_pty_launcher.py   # Real PTY operations
│   │   └── test_signal_handling.py
│   └── windows/
│       ├── conftest.py            # Auto-applies @pytest.mark.windows_only
│       └── test_file_locking.py
│
├── e2e/
│   ├── conftest.py                # Auto-applies @pytest.mark.e2e
│   └── test_spawn_lifecycle.py    # Full CLI spawn create/list/show
│
└── support/                       # Shared utilities (NOT imported as conftest)
    ├── __init__.py
    ├── fakes.py                   # FakeClock, FakeFileAdapter, FakeSubprocess
    ├── fixtures.py                # Factory fixtures for state roots, spawn records
    └── assertions.py              # Custom assertion helpers
```

---

## Key Technical Decisions

### 1. Protocol vs ABC

**Decision:** Use `typing.Protocol` for all adapter interfaces, not `abc.ABC`.

**Rationale:**
- Structural subtyping — implementations don't need to inherit, just match signature
- Cleaner testing — fakes automatically satisfy protocol if they have the methods
- Consistent with existing `ArtifactStore` pattern in the codebase

### 2. Adapter Construction

**Decision:** Adapters are constructed at composition root, not in modules.

**Rationale:**
- Production code never imports fakes
- Tests inject fakes via fixtures
- No conditional imports based on test vs production

**Example:**
```python
# Production (cli/main.py)
from meridian.lib.launch.streaming.adapters import RealClock, RealHeartbeatAdapter
runner = StreamingRunner(clock=RealClock(), heartbeat=RealHeartbeatAdapter())

# Test
from tests.support.fakes import FakeClock, FakeHeartbeatAdapter
runner = StreamingRunner(clock=FakeClock(), heartbeat=FakeHeartbeatAdapter())
```

### 3. Clock Protocol Scope

**Decision:** Single `Clock` protocol shared across all modules.

**Rationale:**
- Avoids duplicate definitions
- Single fake implementation in tests
- Lives in `lib/core/clock.py` as shared infrastructure

**Interface:**
```python
class Clock(Protocol):
    def monotonic(self) -> float: ...
    def time(self) -> float: ...
    def utc_now_iso(self) -> str: ...
```

### 4. Pure Event Reducer

**Decision:** `_record_from_events()` becomes public `reduce_events()` in `state/spawn/events.py`.

**Rationale:**
- Currently the most valuable pure logic buried in spawn_store.py
- Enables testing projection logic without filesystem
- Prepares for future event replay/migration tooling

### 5. Marker Auto-Application

**Decision:** Directory-based markers applied via pytest hooks, not decorators on every test.

**Rationale:**
- Less boilerplate — tests inherit markers from location
- Enforces convention — can't have unit test with real I/O in tests/unit/
- Explicit override via decorator when needed

**Implementation:**
```python
# tests/unit/conftest.py
def pytest_collection_modifyitems(items):
    for item in items:
        if "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
```

### 6. Support Module vs conftest.py

**Decision:** Shared code lives in `tests/support/` modules, NOT in conftest.py.

**Rationale:**
- conftest.py imports are implicit and fragile
- Support modules have explicit imports
- Easier to understand test dependencies

---

## CI Configuration

### Fast Gate (Every PR)
```yaml
test-fast:
  runs-on: ubuntu-latest
  steps:
    - run: pytest -m "unit or (integration and not slow)" --timeout=60
```

### Full Gate (Merge Queue)
```yaml
test-full:
  strategy:
    matrix:
      os: [ubuntu-latest, windows-latest]
  steps:
    - if: matrix.os == 'ubuntu-latest'
      run: pytest -m "not windows_only" --timeout=300
    - if: matrix.os == 'windows-latest'
      run: pytest -m "not posix_only" --timeout=300
```

---

## Files Created/Modified

### New Files
| Path | Purpose |
|------|---------|
| `src/meridian/lib/core/clock.py` | Shared Clock protocol + RealClock impl |
| `src/meridian/lib/launch/streaming/decision.py` | Pure retry/terminal logic |
| `src/meridian/lib/launch/streaming/heartbeat.py` | Injectable heartbeat manager |
| `src/meridian/lib/launch/streaming/adapters.py` | Protocol definitions |
| `src/meridian/lib/launch/streaming/runner.py` | Thin orchestration shell |
| `src/meridian/lib/launch/process/pty_launcher.py` | PTY mechanics |
| `src/meridian/lib/launch/process/session.py` | Session management |
| `src/meridian/lib/launch/process/ports.py` | ProcessLauncher protocol |
| `src/meridian/lib/launch/process/runner.py` | Thin orchestration |
| `src/meridian/lib/state/spawn/events.py` | Pure event reducer |
| `src/meridian/lib/state/spawn/repository.py` | File I/O adapter |
| `src/meridian/lib/state/spawn/adapters.py` | FileAdapter, LockAdapter protocols |
| `src/meridian/lib/state/spawn/store.py` | Composition layer |
| `tests/support/fakes.py` | FakeClock, FakeFileAdapter, etc. |
| `tests/support/fixtures.py` | Factory fixtures |
| `tests/unit/conftest.py` | Auto-marker application |
| `tests/integration/conftest.py` | Auto-marker application |
| etc. | (directory conftest.py files) |

### Modified Files
| Path | Change |
|------|--------|
| `src/meridian/lib/launch/streaming_runner.py` | Becomes thin re-export for backward compat |
| `src/meridian/lib/launch/process.py` | Becomes thin re-export for backward compat |
| `src/meridian/lib/state/spawn_store.py` | Becomes thin re-export for backward compat |
| `tests/conftest.py` | Add marker registration |
| `.github/workflows/ci.yml` | Update test commands |

---

## Backward Compatibility

The original module paths remain as re-exports:

```python
# src/meridian/lib/launch/streaming_runner.py (after refactor)
"""Backward compatibility re-exports."""
from meridian.lib.launch.streaming.runner import (
    execute_with_streaming,
    run_streaming_spawn,
)
from meridian.lib.launch.streaming.decision import (
    terminal_event_outcome,
    TerminalEventOutcome,
)

__all__ = [
    "execute_with_streaming",
    "run_streaming_spawn",
    "terminal_event_outcome",
    "TerminalEventOutcome",
]
```

This allows existing imports to continue working during migration.
