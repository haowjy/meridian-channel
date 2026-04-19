# Test Architecture Overhaul — Requirements

## Problem Statement

The current test suite (570 tests, ~20k lines) was built ad-hoc without a coherent philosophy. It suffers from:

1. **Structural incoherence** — Top-level `tests/*.py` catch-all mixes CLI, launch, app, streaming, process concerns
2. **Mixed test types** — Unit, integration, contract tests all in one pytest tree without separation
3. **Fixture sprawl** — Most files build bespoke fake objects inline instead of reusing shared fixtures
4. **Production code testability issues** — Monolithic files like `streaming_runner.py` mix orchestration + signals + heartbeat + retry + filesystem + spawn-store, forcing tests to monkeypatch private internals
5. **Naming inconsistency** — Some behavior-oriented, some implementation-oriented, some phase-named (`test_app_agui_phase3.py`)

## Goals

1. **Coherent test architecture** — Clear separation of unit/integration/e2e with directory structure + markers
2. **Improved production code testability** — Refactor monolithic modules into single-purpose files with injectable dependencies
3. **Reusable fixture layer** — Centralized fixtures for common patterns (tmp state roots, fake clocks, subprocess mocks)
4. **Windows testability** — Platform-conditioned tests, simulation where possible, real Windows CI for what can't be simulated
5. **Sustainable test economics** — Fast unit tests as gate, slower integration tests in CI, sparse e2e for critical paths

## Design Principles (from research)

### Testing Philosophy

1. **Functional core / imperative shell** (Gary Bernhardt) — Put branching logic in pure functions, IO in thin shell. Maximize fast deterministic tests.
2. **Classicist baseline, mockist at boundaries** — Use real collaborators where cheap, mock at architectural boundaries
3. **Test Desiderata** (Kent Beck) — Tests optimize trade-offs: isolated, deterministic, fast, writable, readable, predictive
4. **Integrated tests are sparse** (Rainsberger) — Keep e2e thin, emphasize isolated tests + contracts
5. **Avoid test-induced design damage** (DHH) — Each abstraction must justify runtime/business value, not just easier mocking

### Pytest Conventions

1. **Directory structure** — Organize by domain boundary, not test type alone. Use both directories AND markers.
2. **conftest.py layers** — Small root for global fixtures, per-directory for domain-specific
3. **Fixture discipline** — Default to `function` scope, `yield` cleanup, factory fixtures for multi-instance
4. **Don't import conftest** — Put helpers in explicit modules (`tests/support/`)
5. **Naming** — Behavior-oriented names (`test_spawn_times_out_and_returns_retryable_error`)

### Design-for-Testability

1. **Make dependencies explicit** — Constructor/parameter injection, not globals/singletons
2. **Separate orchestration from logic** — Pure decision functions + thin IO shell
3. **Inject configuration** — Parse env once at composition root, pass typed config down
4. **Time/randomness/IO as dependencies** — `Clock`, `FileSystem` as injectable ports
5. **Single-purpose files** — Each file should have one clear responsibility

### Windows Testing

1. **Can simulate on Linux** — Platform detection, Windows path parsing, pyfakefs
2. **Needs real Windows** — Process/signal semantics, file locking, NTFS edge cases
3. **Strategy** — Linux CI as broad fast gate, Windows CI as narrow targeted gate

## Current State Analysis

### Test Coverage Distribution (570 tests)

| Area | Count | Notes |
|------|-------|-------|
| `tests/harness/` | 145 | Heavy coverage |
| `tests/*.py` (root) | 139 | Incoherent catch-all — needs restructuring |
| `tests/test_state/` | 106 | Good coverage |
| `tests/exec/` | 76 | Good coverage |
| `tests/ops/` | 71 | Good coverage |
| `tests/server/`, `tests/prompt/`, `tests/unit/` | sparse | Coverage gaps |

### Production Code Testability Hotspots

| Priority | File | Problem | Pattern to Apply |
|----------|------|---------|------------------|
| 🔴 1 | `streaming_runner.py` | Mixes orchestration + signals + heartbeat + retry + FS + spawn-store. Tests monkeypatch `_HEARTBEAT_INTERVAL_SECS`, `_touch_heartbeat_file`. | Split into **pure decision engine** + injected adapters |
| 🔴 2 | `process.py` | PTY/subprocess coupled to OS. Direct `time.time()`, `sys.stdin/stdout`, `os.fork()`. | Isolate behind **narrow interface**, inject clocks |
| 🟡 3 | `spawn_store.py` + `reaper.py` | Persistence + projection + transition policy coupled. Direct FS, locking, time, env. | **Repository adapter** for file I/O, inject clock/depth |
| 🟡 4 | `cli/main.py` | Subprocess execution, env mutation inline | **Runner object** wrapper, explicit env context |

## Target Architecture

### Test Directory Structure

```
tests/
  conftest.py              # Global: env isolation, platform markers, strict_markers
  
  unit/                    # Pure logic, parsing, data transforms — no real IO
    conftest.py            # Unit-specific fixtures (fake clocks, mock adapters)
    state/                 # State layer unit tests
    launch/                # Launch decision logic
    harness/               # Harness projection/parsing
    
  integration/             # One real boundary at a time — real tmp_path, controlled subprocess
    conftest.py            # Integration fixtures (state root factory, subprocess sandbox)
    state/                 # State store with real filesystem
    launch/                # Launch with real subprocess
    cli/                   # CLI invocation tests
    
  contract/                # Parity, drift, invariant checks
    harness/               # Launch spec parity tests
    
  platform/                # Windows/POSIX specific
    conftest.py            # Platform markers
    
  e2e/                     # Installed CLI as users run it — sparse, critical paths only
    
  support/                 # Shared utilities (NOT conftest imports)
    fixtures.py            # Reusable fixture factories
    fakes.py               # Fake clock, fake subprocess, fake filesystem
    assertions.py          # Custom assertion helpers
```

### Markers

```python
# tests/conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: pure logic tests, no IO")
    config.addinivalue_line("markers", "integration: one real boundary")
    config.addinivalue_line("markers", "e2e: full CLI invocation")
    config.addinivalue_line("markers", "contract: parity/drift checks")
    config.addinivalue_line("markers", "posix_only: requires POSIX")
    config.addinivalue_line("markers", "windows_only: requires Windows")
    config.addinivalue_line("markers", "slow: takes >1s")
```

### CI Matrix

```yaml
# Fast gate (every PR)
- ubuntu-latest: pytest -m "unit or (integration and not slow)"

# Full gate (merge queue / nightly)
- ubuntu-latest: pytest -m "not windows_only"
- windows-latest: pytest -m "not posix_only"
```

### Production Code Refactoring Targets

#### streaming_runner.py → Split into:

1. `launch/streaming/decision.py` — Pure decision logic (retry policy, state transitions)
2. `launch/streaming/heartbeat.py` — Heartbeat management with injectable clock
3. `launch/streaming/runner.py` — Thin orchestration shell composing the above
4. `launch/streaming/adapters.py` — Interfaces for clock, sleep, signals, spawn-store

#### process.py → Split into:

1. `launch/process/pty_launcher.py` — PTY/subprocess mechanics behind interface
2. `launch/process/session.py` — Session management
3. `launch/process/runner.py` — Thin orchestration composing the above
4. `launch/ports.py` — Clock, ProcessLauncher protocols

#### spawn_store.py → Split into:

1. `state/spawn/events.py` — Pure event reducer (`_record_from_events`)
2. `state/spawn/repository.py` — File I/O adapter
3. `state/spawn/store.py` — Thin composition layer

### Shared Fixtures

```python
# tests/support/fakes.py

class FakeClock:
    """Injectable clock for deterministic time tests."""
    def __init__(self, start: float = 0.0):
        self._now = start
    
    def now(self) -> float:
        return self._now
    
    def advance(self, seconds: float) -> None:
        self._now += seconds

class FakeFileSystem:
    """Injectable filesystem for unit tests."""
    ...

class FakeSubprocess:
    """Injectable subprocess runner for unit tests."""
    ...
```

```python
# tests/unit/conftest.py

@pytest.fixture
def fake_clock():
    return FakeClock()

@pytest.fixture
def fake_fs(tmp_path):
    return FakeFileSystem(root=tmp_path)
```

## Success Criteria

1. **Structure** — All 570+ tests classified into unit/integration/contract/platform/e2e
2. **Markers** — `pytest -m unit` runs in <30s, `pytest -m integration` <2min
3. **Fixtures** — Common patterns (state root, clock, subprocess) available as shared fixtures
4. **Testability** — `streaming_runner.py` and `process.py` split, tests no longer monkeypatch private internals
5. **Windows** — Platform tests pass on Windows CI, platform detection mockable on Linux
6. **No regressions** — All existing test behaviors preserved

## Constraints

1. **Incremental migration** — Tag first, move folders second, rewrite brittle tests third
2. **No test-induced damage** — Each production abstraction must justify runtime value
3. **Preserve coverage** — Don't delete tests without replacement
4. **Single-purpose files** — Each new file has one clear responsibility

## Out of Scope

- Fixing all Windows compatibility issues (separate work item)
- Adding property-based testing (future enhancement)
- Full e2e test suite (keep sparse)
