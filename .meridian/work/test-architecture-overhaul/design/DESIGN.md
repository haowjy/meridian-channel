# Test Architecture & Code Extensibility Overhaul

**Status:** Draft  
**Author:** dev-orchestrator  
**Date:** 2026-04-19  
**Work Item:** test-architecture-overhaul

---

## Executive Summary

This design addresses three interconnected problems in meridian-cli:

1. **Test Architecture** — 570 tests built ad-hoc without coherent philosophy
2. **Code Testability** — Monolithic modules force tests to monkeypatch private internals
3. **Code Extensibility** — Entangled concerns block future features (Windows ConPTY, new harnesses, remote workers)

The solution is a unified refactoring that improves all three by applying the **functional core / imperative shell** pattern: extract pure decision logic into testable units, inject dependencies through explicit interfaces, and organize tests by behavioral layer.

---

## Research Summary

### Sources Consulted

| Category | Sources |
|----------|---------|
| **Testing Philosophy** | Kent Beck (Test Desiderata), Gary Bernhardt (Boundaries), J.B. Rainsberger (Integrated Tests Scam), Martin Fowler (Test Pyramid, Mocks Aren't Stubs) |
| **Pytest Conventions** | pytest docs, requests/flask/pytest repos as exemplars |
| **Design Patterns** | Michael Feathers (Seams), Alistair Cockburn (Hexagonal Architecture), DHH (Test-Induced Design Damage warning) |
| **Windows Testing** | Python docs, pyfakefs docs, platform simulation limits |

### Key Principles Adopted

1. **Functional Core / Imperative Shell** — Put branching logic in pure functions, IO in thin shell
2. **Classicist Baseline, Mockist at Boundaries** — Real collaborators where cheap, mock at architectural seams
3. **Each File Has One Purpose** — Single responsibility, independently extensible
4. **Test Desiderata** — Isolated, deterministic, fast, writable, readable, predictive
5. **No Test-Induced Design Damage** — Every abstraction must justify runtime/business value

---

## Current State Analysis

### Codebase Consistency (Good)

| Area | Status |
|------|--------|
| Naming conventions | ✅ Clean — snake_case functions, PascalCase classes, underscore-prefixed internals |
| Type annotations | ✅ 99.8% coverage, PEP 604 `| None` standardized |
| Protocol vs ABC | ✅ Consistent — Protocol for contracts, ABC only where inheritance needed |
| Import organization | ✅ stdlib → third-party → local ordering |
| Error handling | ✅ Narrow custom exceptions, centralized `ErrorCategory` |
| Dependency injection | ✅ Immutable context bundles (`RuntimeContext`, `LaunchContext`) |

### Test Suite Problems

| Problem | Evidence |
|---------|----------|
| **Structural incoherence** | 139 tests in `tests/*.py` catch-all mixing CLI, launch, app, streaming |
| **Mixed test types** | Unit, integration, contract tests in one pytest tree without separation |
| **Fixture sprawl** | Most files build bespoke fake objects inline |
| **Private monkeypatching** | Tests patch `_HEARTBEAT_INTERVAL_SECS`, `_touch_heartbeat_file`, `_run_primary_process_with_capture` |
| **Naming inconsistency** | `test_app_agui_phase3.py` — phase-named, not behavior-named |

### Module Extensibility Problems

| Module | Lines | Entanglement | Future Features Blocked |
|--------|-------|--------------|------------------------|
| `streaming_runner.py` | 1244 | 🔴 High — retry, heartbeat, signals, terminal detection all entangled | New harnesses, per-harness retry, HTTP heartbeat |
| `process.py` | 570 | 🟡 Medium-High — PTY, subprocess, session, platform all in one | Windows ConPTY, remote execution |
| `spawn_store.py` | 736 | 🔴 High (persistence) — API assumes local `Path` roots | Remote/SQLite state backend |
| `cli/main.py` | 1515 | 🟡 Mixed concerns — router + mars + launch + bootstrap | Maintainability |
| `spawn/execute.py` | 1012 | 🟡 Medium-High — background/foreground paths diverge | Remote workers, third execution mode |

### One Duplicated Pattern

Lazy Unix-module proxy duplicated in two places:
- `process.py:49`
- `session_store.py:21`

Should be centralized in `lib/platform/`.

---

## Design Goals

### Primary Goals

1. **Testability** — Tests don't monkeypatch private internals
2. **Extensibility** — New harnesses, platforms, backends don't require touching unrelated code
3. **Maintainability** — Each file has one clear purpose

### Success Criteria

| Metric | Target |
|--------|--------|
| Unit test runtime | < 30 seconds |
| Private monkeypatches | 0 |
| Windows CI | Passing |
| New harness addition | Touches only harness + adapter files |

---

## Architecture Design

### Production Code Refactoring

#### Track 1: Shared Infrastructure

**REF-001: Shared Clock Protocol**

```python
# src/meridian/lib/core/clock.py
from typing import Protocol

class Clock(Protocol):
    def monotonic(self) -> float: ...
    def time(self) -> float: ...
    def utc_now_iso(self) -> str: ...

class RealClock:
    def monotonic(self) -> float:
        return time.monotonic()
    def time(self) -> float:
        return time.time()
    def utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
```

**Rationale:** Every module needing testability calls `time.time()` directly. Shared Clock enables consistent `FakeClock` across all tests.

**REF-002: Centralize Lazy Unix Module Proxy**

```python
# src/meridian/lib/platform/unix_modules.py
class _DeferredUnixModule:
    """Lazy module proxy so Unix-only modules load only on demand."""
    ...

fcntl = _DeferredUnixModule("fcntl")
termios = _DeferredUnixModule("termios")
```

**Rationale:** Currently duplicated in `process.py` and `session_store.py`. Single source of truth.

---

#### Track 2: streaming_runner.py Split

**Current:** 1244 lines mixing orchestration + signals + heartbeat + retry + filesystem + spawn-store

**Target Structure:**

```
src/meridian/lib/launch/streaming/
├── __init__.py           # Re-exports for backward compat
├── decision.py           # Pure: terminal_event_outcome(), retry logic
├── heartbeat.py          # HeartbeatBackend protocol + file implementation
├── signals.py            # SignalCoordinator protocol + Unix/Windows implementations
├── adapters.py           # Clock, SpawnStoreAdapter protocols
└── runner.py             # Thin orchestration shell composing above
```

**Key Interfaces:**

```python
# decision.py — Pure, no I/O
def terminal_event_outcome(event: HarnessEvent) -> TerminalEventOutcome: ...
def should_retry(error: ErrorCategory, attempt: int, policy: RetryPolicy) -> bool: ...

# heartbeat.py — Injectable
class HeartbeatBackend(Protocol):
    async def touch(self) -> None: ...
    
class FileHeartbeat:
    def __init__(self, path: Path, clock: Clock): ...

# Future: class HttpHeartbeat for remote monitoring
```

**Extensibility Unlocked:**
- New harness → Add terminal patterns to `decision.py`
- Per-harness retry → Pass different `RetryPolicy`
- HTTP heartbeat → Implement `HeartbeatBackend`
- Windows signals → Implement `SignalCoordinator` for Windows

---

#### Track 3: process.py Split

**Current:** 570 lines mixing PTY/subprocess + session + platform

**Target Structure:**

```
src/meridian/lib/launch/process/
├── __init__.py           # Re-exports
├── ports.py              # Clock, ProcessLauncher protocols
├── pty_launcher.py       # Unix PTY implementation
├── subprocess_launcher.py # Fallback subprocess implementation  
├── session.py            # Session bookkeeping, extracted from run_harness_process
└── runner.py             # Thin orchestration
```

**Key Interfaces:**

```python
# ports.py
class ProcessLauncher(Protocol):
    async def launch(self, cmd: list[str], env: dict) -> LaunchedProcess: ...
    
class LaunchedProcess(Protocol):
    @property
    def pid(self) -> int: ...
    async def wait(self) -> int: ...
    async def terminate(self) -> None: ...

# pty_launcher.py
class PtyLauncher:
    """Unix PTY-based launcher with output capture."""
    
# subprocess_launcher.py  
class SubprocessLauncher:
    """Fallback for Windows or non-interactive."""

# Future: class ConPtyLauncher for Windows ConPTY
# Future: class RemoteLauncher for SSH execution
```

**Extensibility Unlocked:**
- Windows ConPTY → Implement `ProcessLauncher`
- Remote execution → Implement `ProcessLauncher` for SSH
- Different capture modes → Compose different launchers

---

#### Track 4: spawn_store.py Split

**Current:** 736 lines mixing persistence + projection + transitions

**Target Structure:**

```
src/meridian/lib/state/spawn/
├── __init__.py           # Re-exports
├── events.py             # Pure: reduce_events(), event models
├── repository.py         # SpawnRepository protocol + file implementation
└── store.py              # Thin composition
```

**Key Interfaces:**

```python
# events.py — Pure, no I/O
def reduce_events(events: list[SpawnEvent]) -> dict[str, SpawnRecord]: ...

# repository.py — Injectable
class SpawnRepository(Protocol):
    def append_event(self, event: SpawnEvent) -> None: ...
    def read_events(self) -> list[SpawnEvent]: ...
    def next_id(self) -> SpawnId: ...

class FileSpawnRepository:
    def __init__(self, paths: StateRootPaths, clock: Clock): ...

# Future: class SqliteSpawnRepository
# Future: class RemoteSpawnRepository
```

**Extensibility Unlocked:**
- SQLite backend → Implement `SpawnRepository`
- Remote state → Implement `SpawnRepository`
- Unit test projection → Call `reduce_events()` directly

---

#### Track 5: cli/main.py Cleanup

**Current:** 1515 lines mixing router + mars + launch + bootstrap

**Target Structure:**

```
src/meridian/cli/
├── main.py               # Slim: argv parsing, command routing only
├── bootstrap.py          # Startup validation, env setup
├── mars_passthrough.py   # Mars subprocess forwarding
├── primary_launch.py     # Primary session launch policy
└── ... (existing command modules)
```

**Rationale:** Maintainability, not extensibility. Reduces collision risk when changing launch vs mars vs bootstrap logic.

---

### Test Architecture

#### Directory Structure

```
tests/
├── conftest.py              # Global: env isolation, marker registration
├── unit/                    # Pure logic, no real I/O
│   ├── conftest.py          # Auto-marker, FakeClock, FakeRepository
│   ├── state/
│   │   └── test_events.py   # Test reduce_events() pure function
│   ├── launch/
│   │   └── test_decision.py # Test terminal_event_outcome() pure function
│   └── ...
├── integration/             # One real boundary at a time
│   ├── conftest.py          # Auto-marker, real tmp_path
│   ├── state/
│   ├── launch/
│   └── cli/
├── contract/                # Parity, drift, invariant checks
│   └── harness/
├── platform/                # Windows/POSIX specific
│   ├── posix/
│   └── windows/
├── e2e/                     # Sparse, critical paths only
└── support/                 # Shared utilities (NOT conftest)
    ├── fakes.py             # FakeClock, FakeRepository, FakeHeartbeat
    ├── fixtures.py          # Factory fixtures
    └── assertions.py        # Custom assertion helpers
```

#### Markers

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

#### CI Configuration

```yaml
# Fast gate (every PR)
- ubuntu-latest: pytest -m "unit or (integration and not slow)"

# Full gate (merge queue)  
- ubuntu-latest: pytest -m "not windows_only"
- windows-latest: pytest -m "not posix_only"
```

#### Shared Fakes

```python
# tests/support/fakes.py

class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start
    def monotonic(self) -> float:
        return self._now
    def time(self) -> float:
        return self._now
    def utc_now_iso(self) -> str:
        return datetime.fromtimestamp(self._now, tz=timezone.utc).isoformat()
    def advance(self, seconds: float) -> None:
        self._now += seconds

class FakeSpawnRepository:
    def __init__(self):
        self._events: list[SpawnEvent] = []
    def append_event(self, event: SpawnEvent) -> None:
        self._events.append(event)
    def read_events(self) -> list[SpawnEvent]:
        return list(self._events)

class FakeHeartbeat:
    def __init__(self):
        self.touches: list[float] = []
    async def touch(self) -> None:
        self.touches.append(time.monotonic())
```

---

## Implementation Plan

### Phase 0: Foundation (Week 1)

Atomic commits, each passing tests:

| Commit | Change | Validation |
|--------|--------|------------|
| 0.1 | Create `lib/core/clock.py` with `Clock` protocol + `RealClock` | Import works |
| 0.2 | Create `tests/support/` with `__init__.py`, `fakes.py` (FakeClock only) | Import works |
| 0.3 | Add marker registration to `tests/conftest.py` | `pytest --markers` shows them |
| 0.4 | Centralize lazy Unix proxy in `lib/platform/unix_modules.py` | Existing tests pass |
| 0.5 | Update `process.py` to import from `lib/platform/` | Existing tests pass |
| 0.6 | Update `session_store.py` to import from `lib/platform/` | Existing tests pass |

### Phase 1: Pure Logic Extraction (Week 2)

| Commit | Change | Validation |
|--------|--------|------------|
| 1.1 | Create `lib/state/spawn/events.py` with `reduce_events()` | Import works |
| 1.2 | Move `_record_from_events` logic to `events.py`, re-export from `spawn_store.py` | Existing tests pass |
| 1.3 | Add unit tests for `reduce_events()` in `tests/unit/state/` | New tests pass |
| 1.4 | Create `lib/launch/streaming/decision.py` | Import works |
| 1.5 | Move `terminal_event_outcome()` to `decision.py`, re-export | Existing tests pass |
| 1.6 | Add unit tests for `terminal_event_outcome()` in `tests/unit/launch/` | New tests pass |

### Phase 2: Adapter Interfaces (Week 3)

| Commit | Change | Validation |
|--------|--------|------------|
| 2.1 | Create `HeartbeatBackend` protocol in `lib/launch/streaming/heartbeat.py` | Import works |
| 2.2 | Create `FileHeartbeat` implementation | Import works |
| 2.3 | Add `FakeHeartbeat` to `tests/support/fakes.py` | Import works |
| 2.4 | Create `SpawnRepository` protocol in `lib/state/spawn/repository.py` | Import works |
| 2.5 | Create `FileSpawnRepository` implementation | Import works |
| 2.6 | Add `FakeSpawnRepository` to `tests/support/fakes.py` | Import works |

### Phase 3: Injection Points (Week 4)

| Commit | Change | Validation |
|--------|--------|------------|
| 3.1 | Add `clock` parameter to `streaming_runner` functions (default `RealClock()`) | Existing tests pass |
| 3.2 | Add `heartbeat` parameter (default `FileHeartbeat`) | Existing tests pass |
| 3.3 | Update streaming_runner tests to use `FakeClock`, `FakeHeartbeat` | Tests pass, no private monkeypatching |
| 3.4 | Add `clock` parameter to `spawn_store` functions | Existing tests pass |
| 3.5 | Add `repository` parameter (default `FileSpawnRepository`) | Existing tests pass |
| 3.6 | Update spawn_store tests to use fakes | Tests pass |

### Phase 4: Process Module Split (Week 5)

| Commit | Change | Validation |
|--------|--------|------------|
| 4.1 | Create `lib/launch/process/ports.py` with `ProcessLauncher` protocol | Import works |
| 4.2 | Create `lib/launch/process/pty_launcher.py` | Import works |
| 4.3 | Create `lib/launch/process/subprocess_launcher.py` | Import works |
| 4.4 | Extract session logic to `lib/launch/process/session.py` | Import works |
| 4.5 | Create slim `lib/launch/process/runner.py` composing above | Existing tests pass |
| 4.6 | Re-export from original `process.py` for backward compat | Existing tests pass |

### Phase 5: Test Migration (Week 6)

| Commit | Change | Validation |
|--------|--------|------------|
| 5.1 | Create `tests/unit/`, `tests/integration/`, `tests/contract/` directories with conftest.py | Structure exists |
| 5.2 | Move pure logic tests to `tests/unit/` | `pytest -m unit` works |
| 5.3 | Move boundary tests to `tests/integration/` | `pytest -m integration` works |
| 5.4 | Move parity tests to `tests/contract/` | `pytest -m contract` works |
| 5.5 | Tag remaining root tests, move incrementally | Test count preserved |
| 5.6 | Update CI to use marker-based selection | CI passes |

### Phase 6: CLI Cleanup (Week 7)

| Commit | Change | Validation |
|--------|--------|------------|
| 6.1 | Extract `cli/bootstrap.py` | Existing tests pass |
| 6.2 | Extract `cli/mars_passthrough.py` | Existing tests pass |
| 6.3 | Extract `cli/primary_launch.py` | Existing tests pass |
| 6.4 | Slim down `cli/main.py` to router only | Existing tests pass |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Large async function split breaks timing** | Keep timing-sensitive code together, extract only pure logic first |
| **Test migration breaks discovery** | Run `--collect-only` before/after each batch, atomic commits |
| **Backward compat imports break** | Re-export from original paths, test import paths explicitly |
| **Abstraction overhead** | Each interface must justify runtime value (extensibility), not just testability |

---

## Open Questions

1. **Backward compatibility policy** — How long should re-exports remain? Permanent vs deprecation cycle?
2. **Async heartbeat testing** — May need `asyncio-fake-time` or custom helper for `FakeClock` + `asyncio.sleep` interaction
3. **Contract test scope** — Which protocols need contract tests? (Decided: only those with multiple implementations)

---

## Appendix: Windows Testing Strategy

### Can Simulate on Linux

| Area | Technique |
|------|-----------|
| Platform detection | `monkeypatch.setattr(mod.sys, "platform", "win32")` |
| Windows-only modules | `patch.dict(sys.modules, {"winreg": fake})` |
| Windows path parsing | `ntpath`, `PureWindowsPath` |
| Filesystem behavior | pyfakefs with `OSType.WINDOWS` |

### Needs Real Windows CI

| Area | Why |
|------|-----|
| Process/signal semantics | `os.kill` differs, `kill()` == `terminate()` |
| File locking | NTFS semantics differ |
| Console I/O | ConPTY vs PTY |

### CI Matrix

```yaml
matrix:
  os: [ubuntu-latest, windows-latest]
  python-version: ["3.12", "3.14"]
```

---

## References

- [Test Desiderata](https://testdesiderata.com/) — Kent Beck
- [Boundaries](https://www.destroyallsoftware.com/talks/boundaries) — Gary Bernhardt
- [Integrated Tests Are A Scam](https://www.infoq.com/presentations/integration-tests-scam/) — J.B. Rainsberger
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture) — Alistair Cockburn
- [Seams](https://www.informit.com/articles/article.aspx?p=359417&seqNum=3) — Michael Feathers
- [Test-Induced Design Damage](https://dhh.dk/2014/test-induced-design-damage.html) — DHH
- [Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html) — Martin Fowler
- [pytest fixtures](https://docs.pytest.org/en/stable/reference/fixtures.html)
- [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
