# Feasibility Record: Spawn Lifecycle Rearchitecture

## F1: psutil availability and API surface

**Assumption**: psutil provides cross-platform PID liveness with create_time-based reuse detection.

**Probe result**: psutil is not currently in the project's dependencies. Tested import fails with `ModuleNotFoundError`. The library must be added via `uv add psutil`.

**API verification** (from psutil docs and source, confirmed against psutil 5.x/6.x):
- `psutil.pid_exists(pid)` → bool — works on Linux, macOS, Windows
- `psutil.Process(pid).create_time()` → float (epoch) — works on all platforms
- `psutil.Process(pid).is_running()` → bool — checks both existence and PID reuse via create_time
- `psutil.NoSuchProcess` — raised when PID doesn't exist
- `psutil.AccessDenied` — raised when process exists but can't be inspected
- `psutil.ZombieProcess` — subclass of NoSuchProcess, raised for zombies

**Verdict**: ✅ Feasible. psutil is the de facto standard (~200M downloads/month), pure C extension with no transitive deps. All needed APIs are stable across psutil 5.x and 6.x. Cross-platform coverage is proven.

**Risk**: psutil is a compiled C extension — it needs platform-appropriate wheels. PyPI provides pre-built wheels for all major platforms (manylinux, macOS universal2, Windows x86/x64). Build-from-source fallback requires a C compiler.

## F2: Event stream atomicity for `exited` event

**Assumption**: Writing the `exited` event to `spawns.jsonl` immediately after process exit is safe under concurrent readers.

**Probe result**: `append_event()` in `event_store.py` uses `fcntl.flock` (file lock) + atomic append. This is the same mechanism used for `start`, `update`, and `finalize` events. The `exited` event uses the same path.

**Concern**: On Windows, `fcntl.flock` doesn't exist. The event store would need a Windows-compatible locking mechanism.

**Verdict**: ✅ Feasible for Linux/macOS. ⚠️ Windows file locking needs separate attention — but this is a pre-existing limitation of the entire event store, not specific to this change. The event store already doesn't work on Windows. The psutil change is orthogonal.

## F3: runner_pid correctness

**Assumption**: `os.getpid()` in the runner accurately identifies the process responsible for finalization.

**Analysis**:
- **Foreground spawns**: `execute_with_finalization` runs in the foreground process. `os.getpid()` is the runner. Finalization happens in the `finally` block of the same process. ✅ Correct.
- **Background spawns**: `_background_worker_main` → `execute_with_finalization`. The background worker process IS the runner. `os.getpid()` is correct. The wrapper_pid recorded earlier is the same process. ✅ Correct.
- **Primary launches**: `run_harness_process` in process.py. The primary launch process IS the runner. `os.getpid()` is correct. ✅ Correct.
- **Streaming runner**: `execute_with_streaming` runs in the same process. `os.getpid()` is the runner. ✅ Correct.

**Verdict**: ✅ Feasible. `os.getpid()` correctly identifies the finalizing process in all four launch paths.

## F4: `exited` event timing — is it early enough?

**Assumption**: Writing `exited` immediately after `spawn_and_stream` returns closes the race window.

**Analysis of the current race** (from orphan-investigation.md):
1. Harness subprocess exits
2. `wait_for_process_returncode` polls `process.returncode` — detects exit
3. `spawn_and_stream` enters finally block — drains pipes (may take minutes for inherited descriptors)
4. `spawn_and_stream` returns `SpawnResult`
5. Report extraction begins
6. Report persisted to `report.md`
7. `finalize_spawn` appended

The race occurs between steps 1-4 (harness dead, pipes draining) and step 7 (finalize). The reaper sees dead harness PID during this window.

**With `exited` event at step 4** (after `spawn_and_stream` returns):
- The race window is steps 1-4 (same as before for the harness PID check)
- But the reaper now knows: once `exited` lands, switch to checking runner PID, which is alive through step 7
- The problematic window (steps 4-7: report extraction) is now covered by runner liveness

**Remaining gap**: Steps 1-4 (harness dead, pipes still open, no `exited` yet). During this window, the reaper could still see a dead harness PID. However:
- The runner PID is alive during this window (it's inside `spawn_and_stream`)
- The reaper checks `runner_pid` first when available → runner alive → no orphan stamp
- For legacy spawns without `runner_pid`, the startup grace + PID liveness fallback applies

**Verdict**: ✅ Feasible. The `exited` event at step 4 plus runner_pid liveness eliminates the race. The remaining steps 1-4 gap is covered by runner_pid being alive.

## F5: Pipe drain timeout interaction

**Assumption**: `spawn_and_stream` always returns (doesn't hang indefinitely).

**Probe result**: `POST_EXIT_PIPE_DRAIN_TIMEOUT_SECONDS` is used in `asyncio.wait` with a timeout for pipe drain tasks. If pipes don't drain within the timeout, tasks are cancelled and `spawn_and_stream` returns with whatever was captured. This timeout ensures `spawn_and_stream` always returns.

**Verdict**: ✅ Feasible. The pipe drain timeout guarantees `spawn_and_stream` returns, so `exited` event will always be written (barring process crash, which is the genuine orphan case).

## F6: Heartbeat removal safety

**Assumption**: Removing heartbeat files doesn't break any functionality beyond reaper staleness detection.

**Probe result**: Grepped for all `heartbeat` references:
- `reaper.py`: `_spawn_is_stale` checks heartbeat mtime, `_recent_spawn_activity` checks heartbeat mtime
- `runner.py`: `heartbeat_scope` context manager
- `streaming_runner.py`: `heartbeat_scope` context manager
- `process.py`: `threaded_heartbeat_scope` context manager
- `heartbeat.py`: the module itself
- `spawn_store.py`: `_TERMINAL_RUNTIME_ARTIFACTS` includes `"heartbeat"`
- `output.py`: display formatting references heartbeat
- `sink.py`: heartbeat touch in output sink

**The `sink.py` reference**: `OutputSink` has a `heartbeat()` method that touches the heartbeat file. This is called during output processing to prove the spawn is still alive.

**Verdict**: ⚠️ Needs attention. The `OutputSink.heartbeat()` path must also be cleaned up. The heartbeat mechanism is used in two ways: (1) periodic touch from heartbeat_scope, and (2) on-activity touch from OutputSink. Both are eliminated — the `exited` event replaces the need for filesystem-based liveness signaling.

## F7: `bg-worker-params.json` — is it a runtime file?

**Assumption**: `bg-worker-params.json` is consumed once at background worker startup, not used for ongoing coordination.

**Probe result**: `_load_bg_worker_params` reads it once in `_background_worker_main`. It's read at startup, never again. It contains serialized launch parameters, not runtime state.

**Verdict**: ✅ Not a runtime coordination file. It's a launch artifact, kept in spawn directory. Comparable to `params.json` and `prompt.md`.

## F8: `_TERMINAL_RUNTIME_ARTIFACTS` cleanup consumers

**Assumption**: Removing `cleanup_terminal_spawn_runtime_artifacts` doesn't break call sites.

**Action needed**: Find and remove all call sites. The function is called after finalization to clean up stale PID/heartbeat files. With no such files, all call sites become dead code.

**Verdict**: ⚠️ Must grep all callers and remove them during implementation.

## Open Questions

### Q1: Windows file locking

The event store uses `fcntl.flock`, which is Unix-only. Adding psutil for cross-platform process liveness doesn't fix the file locking gap. This is a pre-existing limitation, not introduced by this change, but it's worth noting for the Windows requirement.

**Recommendation**: Track as a separate work item. The psutil change is independently valuable for macOS PID-reuse detection even without Windows file locking.

### Q2: OutputSink heartbeat

The `OutputSink` class has a heartbeat method. Need to verify during implementation whether removing it affects any consumer or if it's purely advisory.

**Recommendation**: If OutputSink.heartbeat() is called from non-reaper paths (e.g., harness adapters), stub it out rather than remove it, to avoid breaking the adapter interface.
