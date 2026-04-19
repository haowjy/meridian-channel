# Phase 3: Injection Points

## Objective
Add clock, heartbeat, and repository parameters with defaults to streaming_runner and spawn_store functions.

## Commits (Execute in Order)

### Commit 3.1: Add clock Parameter to streaming_runner Functions
Update `streaming_runner.py`:
- Add `clock: Clock | None = None` parameter to `_touch_heartbeat_file`
- Add `clock: Clock | None = None` parameter to `execute_with_streaming`
- Use `clock or RealClock()` internally
- Replace direct `time.time()` and `time.monotonic()` calls with clock methods

Validation: Existing tests pass

### Commit 3.2: Add heartbeat Parameter to streaming_runner
Update `streaming_runner.py`:
- Add `heartbeat: HeartbeatBackend | None = None` parameter
- Use `heartbeat or FileHeartbeat(path)` internally
- Replace `_touch_heartbeat_file` calls with `heartbeat.touch()`

Validation: Existing tests pass

### Commit 3.3: Update streaming_runner Tests to Use Fakes
Update `tests/exec/test_streaming_runner.py`:
- Remove monkeypatches of `_HEARTBEAT_INTERVAL_SECS`
- Remove monkeypatches of `_touch_heartbeat_file`
- Pass `FakeClock` and `FakeHeartbeat` via parameters
- Make heartbeat interval configurable via parameter

Validation: Tests pass without private monkeypatching

### Commit 3.4: Add clock Parameter to spawn_store Functions
Update `spawn_store.py`:
- Add `clock: Clock | None = None` parameter to functions that call `utc_now_iso()`
- Replace `utc_now_iso()` calls with `clock.utc_now_iso()`

Validation: Existing tests pass

### Commit 3.5: Add repository Parameter to spawn_store Functions
Update `spawn_store.py`:
- Add `repository: SpawnRepository | None = None` parameter to key functions
- Use `repository or FileSpawnRepository(paths)` internally
- Route through repository methods

Note: This may be a larger change. Evaluate if full repository abstraction is needed at this phase or if simpler injection points suffice.

Validation: Existing tests pass

### Commit 3.6: Update spawn_store Tests to Use Fakes
Update `tests/test_state/test_spawn_store.py`:
- Where possible, use `FakeClock` instead of time monkeypatches
- Where possible, use `FakeSpawnRepository` for unit tests of projection logic
- Keep integration tests that need real filesystem

Validation: Tests pass

## Files to Touch
- Modify: `src/meridian/lib/launch/streaming_runner.py`
- Modify: `src/meridian/lib/state/spawn_store.py`
- Modify: `tests/exec/test_streaming_runner.py`
- Modify: `tests/test_state/test_spawn_store.py`

## Exit Criteria
- All 6 commits made atomically
- Each commit passes pytest
- No tests monkeypatch `_HEARTBEAT_INTERVAL_SECS` or `_touch_heartbeat_file`
- Clock/repository injection points available
