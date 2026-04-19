# Feasibility Record

This document captures probe evidence and validated assumptions that ground the design decisions.

---

## Validated Assumptions

### [V-001] Protocol Pattern Exists in Codebase

**Assumption:** The codebase already uses `typing.Protocol` for injectable interfaces.

**Evidence:**
- `ArtifactStore` in `src/meridian/lib/state/artifact_store.py` (lines 13-24) is a Protocol with `put`, `get`, `exists`, `delete`, `list_artifacts` methods
- `LocalStore` and `MemoryStore` implement the protocol without inheritance
- Pattern is established and consistent with proposed adapter designs

**Verdict:** ✅ Validated — Use same Protocol pattern for Clock, FileAdapter, SpawnStoreAdapter

---

### [V-002] Current Test Monkeypatching Locations

**Assumption:** Tests monkeypatch `_HEARTBEAT_INTERVAL_SECS` and `_touch_heartbeat_file` in streaming_runner.py.

**Evidence:**
Grep results show:
```
tests/exec/test_streaming_runner.py:1592:    monkeypatch.setattr(streaming_runner_module, "_HEARTBEAT_INTERVAL_SECS", 0.02)
tests/exec/test_streaming_runner.py:1593:    monkeypatch.setattr(streaming_runner_module, "_touch_heartbeat_file", _tracked_touch)
tests/exec/test_streaming_runner.py:1808:    monkeypatch.setattr(streaming_runner_module, "_HEARTBEAT_INTERVAL_SECS", 0.01)
... (multiple occurrences)
```

**Verdict:** ✅ Validated — Injectable heartbeat interval and adapter will eliminate these monkeypatches

---

### [V-003] Module Sizes Confirm Refactoring Need

**Assumption:** Target modules are over the 500-line complexity threshold.

**Evidence:**
```
streaming_runner.py: 1244 lines
process.py: 570 lines
spawn_store.py: 737 lines
```

All three exceed 500 lines. `streaming_runner.py` is nearly 2.5x the threshold.

**Verdict:** ✅ Validated — Split is justified by structural health signals

---

### [V-004] _record_from_events is Pure

**Assumption:** The event reducer function in spawn_store.py is pure and can be extracted.

**Evidence:**
- Function signature: `def _record_from_events(events: list[SpawnEvent]) -> dict[str, SpawnRecord]`
- Takes event list, returns record dict
- No filesystem access, no time calls, no side effects
- All state transformation happens via `model_copy(update={...})`

**Verdict:** ✅ Validated — Direct extraction to events.py with public name `reduce_events()`

---

### [V-005] Unix Module Lazy Loading Already Exists

**Assumption:** process.py already handles Unix-only imports safely.

**Evidence:**
```python
class _DeferredUnixModule:
    """Lazy module proxy so Unix-only modules load only on demand."""
    def __init__(self, module_name: str) -> None:
        ...
    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

fcntl = _DeferredUnixModule("fcntl")
termios = _DeferredUnixModule("termios")
```

**Verdict:** ✅ Validated — Existing pattern is sufficient for Windows compatibility

---

### [V-006] Test Count and Distribution

**Assumption:** Test suite has ~570 tests requiring classification.

**Evidence:**
From requirements.md research:
```
| Area | Count | Notes |
|------|-------|-------|
| tests/harness/ | 145 | Heavy coverage |
| tests/*.py (root) | 139 | Incoherent catch-all |
| tests/test_state/ | 106 | Good coverage |
| tests/exec/ | 76 | Good coverage |
| tests/ops/ | 71 | Good coverage |
| tests/server/, tests/prompt/, tests/unit/ | sparse | Coverage gaps |
```

**Verdict:** ✅ Validated — Migration scope confirmed at 570+ tests

---

## Open Questions

### [Q-001] Heartbeat Async Task Cancellation

**Question:** Does HeartbeatManager need special handling for task cancellation during tests?

**Status:** 🟡 To investigate during implementation

**Context:** Async heartbeat loop uses `asyncio.sleep(interval_secs)`. Tests with FakeClock need to:
1. Either mock `asyncio.sleep` to be instant
2. Or use `asyncio.wait_for` with timeout
3. Or advance FakeClock AND tick event loop

**Recommendation:** Design test helper that advances FakeClock and processes pending tasks. Investigate asyncio-fake-time libraries.

---

### [Q-002] Backward Compatibility Import Chain

**Question:** How long should backward-compat re-exports remain?

**Status:** 🟡 Policy decision needed

**Options:**
1. Permanent — Never break existing imports
2. Deprecation cycle — Warn in 1.x, remove in 2.0
3. Migration tool — Script to update imports

**Recommendation:** Start with permanent re-exports. Revisit if maintenance burden is high.

---

### [Q-003] Contract Test Coverage Scope

**Question:** Which protocols need contract tests?

**Status:** 🟢 Decided

**Decision:** Contract tests for protocols with multiple implementations:
- `Clock` — RealClock + FakeClock
- `FileAdapter` — RealFileAdapter + FakeFileAdapter
- `ProcessLauncher` — PtyLauncher + SubprocessLauncher + FakeProcessLauncher

Protocols with single implementation (e.g., SignalCoordinator) can skip contract tests.

---

### [Q-004] Windows CI Matrix Scope

**Question:** What Windows-specific tests need real Windows CI?

**Status:** 🟢 Decided based on research

**Tests requiring real Windows:**
1. File locking behavior (NTFS semantics differ)
2. Signal handling (no SIGTERM/SIGINT, use taskkill)
3. Process termination (no SIGKILL)
4. Console I/O (no PTY)

**Tests that can simulate Windows on Linux:**
1. Platform detection logic
2. Windows path parsing
3. Feature capability checks

---

## Risks and Mitigations

### [R-001] Large Async Function Split

**Risk:** Splitting `_run_streaming_attempt()` (234 lines) may break subtle timing dependencies.

**Mitigation:**
1. Keep timing-sensitive code together in runner.py
2. Extract only pure decision logic to decision.py
3. Comprehensive integration tests before/after comparison
4. Git bisect-friendly commits (one logical change per commit)

---

### [R-002] Test Migration Regression

**Risk:** Moving tests to new directories could break test discovery or fixtures.

**Mitigation:**
1. Run full test suite after each migration batch
2. Preserve exact test count (--collect-only before/after)
3. Tag phase before move phase
4. Atomic commits per batch

---

### [R-003] Fixture Proliferation

**Risk:** Too many fixtures makes tests hard to understand.

**Mitigation:**
1. Limit to essential fakes (Clock, FileAdapter, SpawnStoreAdapter, HeartbeatAdapter, ProcessLauncher)
2. Factory fixtures for stateful objects
3. No fixture for anything that can be constructed inline
4. Clear naming: `fake_` prefix for test doubles

---

## Probe Results

### [P-001] streaming_runner.py Dependency Analysis

**Probe:** Analyze imports and identify pure vs impure functions.

**Result:**
Pure functions (extractable to decision.py):
- `terminal_event_outcome()` — Classifies HarnessEvent, returns TerminalEventOutcome
- `_stringify_terminal_error()` — String normalization
- (from errors.py) `classify_error()`, `should_retry()`

Impure functions (stay in runner.py):
- `_touch_heartbeat_file()` — Filesystem
- `_install_signal_handlers()` — Signal registration
- `_run_streaming_attempt()` — Async orchestration
- `execute_with_streaming()` — Main entry point

**Action:** Extract pure functions first, then make impure functions accept injectable adapters.

---

### [P-002] spawn_store.py Dependency Analysis

**Probe:** Analyze which functions need file I/O.

**Result:**
Pure (extractable):
- `_record_from_events()` — Event reduction
- `_empty_record()` — Record construction
- `_spawn_sort_key()` — Sorting
- `_normalized_work_id()` — String normalization
- `_coerce_launch_mode()` — Enum coercion
- `_parse_event()` — JSON → Event parsing

Impure (need adapter):
- `next_spawn_id()` — Reads file to count events
- `start_spawn()` — Appends event under lock
- `update_spawn()` — Appends event
- `finalize_spawn()` — Reads + validates + appends
- `list_spawns()` — Reads all events
- `get_spawn()` — Wrapper around list_spawns

**Action:** All event models + reducer → events.py. File operations → repository.py with adapters.
