# Test Architecture Overhaul — Plan v2

**Revision:** Rip out and rewrite, not migrate

---

## Problem with v1 Approach

The impl-orch did file reorganization, not test overhaul:
- Moved some files to `unit/`, `integration/`, `contract/`
- Created fakes but didn't update tests to use them
- Left old tests intact (787 tests = duplicates + old mess)
- No principles applied (Test Desiderata, functional core, etc.)

**Result:** Worse than before — two structures, inflated count, no quality improvement.

---

## v2 Approach: Refactor + Rip Out + Rewrite

### What We Keep

**Production code refactoring (already done):**
- `Clock` protocol + `RealClock`
- `HeartbeatBackend` protocol + `FileHeartbeat`
- `SpawnRepository` protocol + `FileSpawnRepository`
- `ProcessLauncher` protocol + `PtyLauncher`, `SubprocessLauncher`
- Pure functions: `reduce_events()`, `terminal_event_outcome()`
- CLI splits: `bootstrap.py`, `mars_passthrough.py`, `primary_launch.py`

**Test infrastructure (already done):**
- `tests/support/fakes.py` — FakeClock, FakeHeartbeat, FakeSpawnRepository
- `tests/conftest.py` — marker registration
- Directory structure: `unit/`, `integration/`, `contract/`, `support/`

### What We Delete

**All old unit tests that:**
- Monkeypatch private internals (`_HEARTBEAT_INTERVAL_SECS`, `_touch_heartbeat_file`)
- Test implementation details instead of behavior
- Are duplicates from partial migration
- Live in old directories (`tests/harness/`, `tests/exec/`, `tests/test_state/`, etc.)

**Estimate:** Delete ~500 tests, keep ~100-150 integration/contract tests

### What We Write Fresh

New unit tests following principles:
- Test Desiderata: isolated, deterministic, fast, readable
- Functional core: test pure functions extensively
- Behavior naming: `test_spawn_records_failure_when_harness_exits_nonzero`
- Use fakes: FakeClock, FakeHeartbeat, FakeSpawnRepository
- No monkeypatching private internals

---

## Execution Plan

### Phase 1: Clean Up Directory Mess

1. Delete all old test directories:
   ```
   rm -rf tests/harness/
   rm -rf tests/exec/
   rm -rf tests/ops/
   rm -rf tests/test_state/
   rm -rf tests/test_launch/
   rm -rf tests/test_ops/
   rm -rf tests/test_space/
   rm -rf tests/lib/
   rm -rf tests/cli/
   rm -rf tests/config/
   rm -rf tests/prompt/
   rm -rf tests/server/
   rm -rf tests/space/
   ```

2. Delete root-level test files:
   ```
   rm tests/test_*.py
   ```

3. Keep only:
   ```
   tests/
   ├── unit/
   ├── integration/
   ├── contract/
   ├── platform/
   ├── support/
   ├── smoke/           # markdown guides
   └── conftest.py
   ```

### Phase 2: Audit What Remains

After deletion, audit remaining tests in `unit/`, `integration/`, `contract/`:
- Remove any that still monkeypatch privates
- Remove duplicates
- Verify all use proper fakes

### Phase 3: Write New Unit Tests

For each pure function extracted:

**state/spawn/events.py:**
- `test_reduce_events_*` — comprehensive coverage of event reduction

**launch/streaming/decision.py:**
- `test_terminal_event_outcome_*` — all terminal event patterns
- `test_should_retry_*` — retry policy logic

**launch/streaming/heartbeat.py:**
- `test_file_heartbeat_*` — using FakeClock

**state/spawn/repository.py:**
- `test_file_spawn_repository_*` — using tmp_path

**launch/process/:**
- `test_pty_launcher_*` — platform-appropriate
- `test_subprocess_launcher_*`

### Phase 4: Write Integration Tests

For each module boundary:
- CLI → spawn execution
- spawn execution → harness connection
- State store → filesystem

### Phase 5: Verify

- `pytest --collect-only` — target ~200-300 tests, not 787
- `pytest -m unit` — fast (<30s)
- `pytest -m integration` — all pass
- No monkeypatch of private internals anywhere

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Total test count | 200-300 (not 787) |
| Unit test runtime | <30s |
| Private monkeypatches | 0 |
| Tests using fakes | 100% of unit tests |
| Directory structure | Clean (no old dirs) |

---

## Who Does What

- **Phase 1 (cleanup):** Coder — mechanical deletion
- **Phase 2-5 (design + write):** unit-test-orch — apply principles, design tests

This is NOT a file migration task. It's a test architecture design task.
