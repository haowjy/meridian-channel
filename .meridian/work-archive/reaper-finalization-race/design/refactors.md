# Refactor Agenda

## RF-1: Extract psutil liveness module (foundational)

**Priority**: Must be done first — all other changes depend on it.

Create `src/meridian/lib/state/liveness.py` with a single `is_process_alive(pid, created_after_epoch)` function. This replaces `_pid_is_alive`, `_get_boot_time`, and the `/proc/stat` parsing in `reaper.py`. The new module is ~15 lines and works cross-platform.

**Dependency**: `psutil` must be added to `pyproject.toml` first.

## RF-2: Add `SpawnExitedEvent` to event store (foundational)

**Priority**: Must be done before runner changes.

Add the new event type, update the event union, update `_parse_event`, add `record_spawn_exited` function, add projection handling in `_record_from_events`, add `runner_pid`/`exited_at`/`process_exit_code` fields to `SpawnRecord` and `SpawnStartEvent`/`SpawnUpdateEvent`.

This is a schema expansion — no migration needed, backward compatible by construction (new fields default to `None`, new event type is skipped by old parsers).

## RF-3: Delete heartbeat module (cleanup)

**Priority**: After runner changes remove all heartbeat_scope usage.

Delete `src/meridian/lib/launch/heartbeat.py` entirely. Remove all imports. Clean up `OutputSink.heartbeat()` references (stub if needed for interface compatibility).

## RF-4: Remove PID file writes from all launch paths (cleanup)

**Priority**: After `runner_pid` is recorded in event stream.

Remove `harness.pid` writes from:
- `runner.py:spawn_and_stream` (line ~290)
- `streaming_runner.py:run_streaming_spawn` (line ~425)
- `process.py:_record_primary_started` (line ~376)

Remove `background.pid` write from:
- `execute.py:execute_spawn_background` (line ~649)

## RF-5: Remove `cleanup_terminal_spawn_runtime_artifacts` (cleanup)

**Priority**: After PID file elimination.

Remove the function from `spawn_store.py`, remove the `_TERMINAL_RUNTIME_ARTIFACTS` constant, remove all call sites. With no runtime files in spawn directories, there's nothing to clean up.

## RF-6: Rewrite reaper (the payoff)

**Priority**: After RF-1, RF-2, and the runner changes that write `exited` events.

Replace the entire reaper module — all 500 lines — with the simplified ~60-line version. This is the final step that eliminates the state machine.

**Sequencing note**: RF-6 should be the last refactor because the reaper must handle both old-style spawns (no `exited` event) and new-style spawns during the transition. The new reaper handles both via the pre-exit/post-exit branching.
