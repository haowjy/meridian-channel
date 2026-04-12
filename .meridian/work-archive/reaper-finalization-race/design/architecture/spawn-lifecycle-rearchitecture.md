# Architecture: Spawn Lifecycle Rearchitecture

## Overview

This rearchitecture replaces the reaper state machine with a two-event lifecycle protocol in the event stream. The key insight: the reaper's complexity exists because it has to *infer* lifecycle state from indirect signals (PID files, heartbeats, report existence). By making the lifecycle explicit in the event stream, the reaper becomes a trivial liveness guard over a single gap.

```
Before:  start → [running] → ??? → finalize
                               ↑
                    reaper guesses what's happening here
                    using PID files, heartbeat, report.md

After:   start → [running] → exited → [finalizing] → finalize
                                          ↑
                    reaper just checks: is the runner PID alive?
```

## New Event: `exited`

### Schema

```python
class SpawnExitedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    v: int = 1
    event: Literal["exited"] = "exited"
    id: str = ""
    exit_code: int = 0
    exited_at: str | None = None  # ISO 8601 UTC
```

### Semantics

- Written to `spawns.jsonl` immediately when `process.returncode` becomes available (or `wait()` returns).
- **Not a terminal event.** The spawn remains `running` in projection. The `exited` event is an informational lifecycle marker that tells the reaper and display layer: "harness is done, runner is still working."
- Carries only exit code and timestamp. Report content, duration, cost, tokens remain in `finalize`.

### JSONL example

```jsonl
{"v":1,"event":"start","id":"p42","status":"running","worker_pid":12345,"runner_pid":12340,...}
{"v":1,"event":"update","id":"p42","worker_pid":12345}
{"v":1,"event":"exited","id":"p42","exit_code":0,"exited_at":"2026-04-12T14:00:00Z"}
{"v":1,"event":"finalize","id":"p42","status":"succeeded","exit_code":0,...}
```

## SpawnRecord Projection Changes

### New fields on SpawnRecord

```python
class SpawnRecord(BaseModel):
    # ... existing fields ...
    runner_pid: int | None          # PID of the process responsible for finalization
    exited_at: str | None           # timestamp from exited event
    process_exit_code: int | None   # raw exit code from exited event
```

### Projection logic in `_record_from_events`

```python
if isinstance(event, SpawnExitedEvent):
    records[spawn_id] = current.model_copy(
        update={
            "exited_at": event.exited_at or current.exited_at,
            "process_exit_code": event.exit_code if event.exit_code is not None else current.process_exit_code,
        }
    )
    continue
```

The `exited` event does **not** change `status`. The spawn stays `running` until `finalize`.

### `runner_pid` sourcing

The `runner_pid` field is set from the `start` event:

```python
# In SpawnStartEvent
runner_pid: int | None = None
```

- Foreground spawns: `runner_pid = os.getpid()` (the runner process that will finalize)
- Background spawns: `runner_pid = wrapper_pid` (the background wrapper that will finalize)
- Primary launches: `runner_pid = os.getpid()` (the process.py launch process)
- Streaming runner: `runner_pid = os.getpid()` (the streaming runner process)

The `runner_pid` is the process the reaper checks after `exited` lands. It answers: "is the entity responsible for finalization still alive?"

## psutil Liveness Module

### New module: `src/meridian/lib/state/liveness.py`

Replaces all of `_pid_is_alive`, `_get_boot_time`, `_spawn_is_stale`, and related PID helpers in `reaper.py`.

```python
"""Cross-platform process liveness via psutil."""

import psutil

def is_process_alive(pid: int, created_after_epoch: float | None = None) -> bool:
    """Check if a PID is alive, with create_time guard for PID reuse.
    
    Args:
        pid: Process ID to check.
        created_after_epoch: If provided, the process must have been created
            before this epoch timestamp (plus tolerance). Processes created
            after this timestamp are PID-reuse and considered dead.
    
    Returns:
        True if the process exists and passes the create_time guard.
    """
    if not psutil.pid_exists(pid):
        return False
    
    try:
        proc = psutil.Process(pid)
        if created_after_epoch is not None:
            # Process was created after the spawn started = PID reuse
            if proc.create_time() > created_after_epoch + 2.0:  # 2s tolerance
                return False
        return proc.is_running()
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True  # Exists but we can't inspect it
```

### Why psutil

| Concern | Current (`os.kill` + `/proc/stat`) | psutil |
|---|---|---|
| Linux | Works | Works |
| macOS | `os.kill` works, `/proc/stat` doesn't → no PID-reuse guard | Works (uses `sysctl`) |
| Windows | `os.kill` doesn't work for arbitrary PIDs | Works (uses `OpenProcess`) |
| PID-reuse detection | Manual `/proc/stat` parsing, fragile | Built-in `create_time()` |
| Lines of code | ~50 (boot time, clock ticks, tolerance) | ~15 |

### Dependency

`psutil` must be added to project dependencies:

```bash
uv add psutil
```

psutil is a well-established library (200M+ downloads/month), pure C extension, no transitive dependencies. It is already a de facto standard for cross-platform process management in Python.

## Simplified Reaper

### Before: 500 lines, state machine

The current reaper has:
- `_SpawnInspection` dataclass with 12 fields
- `_inspect_spawn_runtime()` — 60 lines of PID file reading and liveness checks
- `_reconcile_background_spawn()` — 45 lines
- `_reconcile_foreground_spawn()` — 40 lines
- `_reconcile_legacy_spawn()` — 16 lines
- 6 helper functions for PID files, boot time, staleness, grace periods
- 3 finalizer helpers

### After: ~30 lines, single function

```python
"""Spawn reconciliation: detect orphaned spawns via process liveness."""

from meridian.lib.state.liveness import is_process_alive

def reconcile_active_spawn(state_root: Path, record: SpawnRecord) -> SpawnRecord:
    """Reconcile one active spawn. Is the responsible process alive?"""
    if not is_active_spawn_status(record.status):
        return record

    started_epoch = _started_at_epoch(record.started_at)

    # Has exited event → runner is doing post-exit finalization
    if record.exited_at is not None:
        if is_process_alive(record.runner_pid, created_after_epoch=started_epoch):
            return record  # Runner alive, will finalize
        # Runner dead after exit — check for durable report
        report_text = _read_completion_report(state_root, record.id)
        if has_durable_report_completion(report_text):
            return _finalize_completed_report(state_root, record)
        return _finalize_failed(state_root, record, "orphan_finalization")

    # No exited event → harness should still be running
    if is_process_alive(record.runner_pid, created_after_epoch=started_epoch):
        return record  # Still running
    # Runner dead, no exit event — genuine orphan
    report_text = _read_completion_report(state_root, record.id)
    if has_durable_report_completion(report_text):
        return _finalize_completed_report(state_root, record)
    return _finalize_failed(state_root, record, "orphan_run")
```

### What's eliminated

- **PID file reading**: PIDs come from event stream only
- **Launch mode dispatch**: No separate foreground/background/legacy paths
- **Heartbeat staleness**: No heartbeat files → no staleness check
- **`_SpawnInspection` dataclass**: All data lives on `SpawnRecord`
- **`_resolve_launch_mode()`**: Launch mode is informational, not a reaper dispatch key
- **`_spawn_is_stale()`**: Replaced by definitive `exited` event
- **`_recent_spawn_activity()`**: Replaced by startup grace on `started_at`

## Runner Changes

### `runner.py:execute_with_finalization`

The `exited` event must be written **inside** the `spawn_and_stream` → finalize sequence, specifically right after `spawn_and_stream` returns (process has exited, pipes may still be draining):

```python
# Current flow (simplified):
spawn_result = await spawn_and_stream(...)
# ... report extraction, enrichment, session ID extraction ...
# ... finalize_spawn(...) in finally block

# New flow:
spawn_result = await spawn_and_stream(...)

# IMMEDIATE: record that the harness exited
spawn_store.record_spawn_exited(
    state_root,
    run.spawn_id,
    exit_code=spawn_result.raw_return_code,
)

# ... report extraction, enrichment, session ID extraction (unchanged) ...
# ... finalize_spawn(...) in finally block (unchanged)
```

The `exited` event write must happen:
1. After `spawn_and_stream` returns (process exited, pipes drained or timed out)
2. Before `enrich_finalize` (report extraction)
3. Inside a `suppress(Exception)` so disk errors don't block finalization

### `runner.py:spawn_and_stream` — PID file elimination

Remove `harness.pid` write from line 290:
```python
# REMOVE:
if log_dir is not None:
    atomic_write_text(log_dir / "harness.pid", f"{process.pid}\n")
```

The worker PID is already recorded via `on_process_started` → `mark_spawn_running()`. The PID file was redundant with the event stream.

### `runner.py:execute_with_finalization` — heartbeat elimination

Remove `heartbeat_scope` context manager. The heartbeat was used by the reaper for staleness detection. The `exited` event makes staleness irrelevant: either the process has exited (exited event exists) or it hasn't (check PID directly).

### `runner.py` — `runner_pid` recording

Add `runner_pid=os.getpid()` to the `start_spawn` call or as an `update_spawn` call before execution begins:

```python
spawn_store.update_spawn(
    state_root,
    run.spawn_id,
    runner_pid=os.getpid(),
)
```

### `process.py:run_harness_process` — same changes

1. Remove `harness.pid` write from `_record_primary_started`
2. Remove `threaded_heartbeat_scope`
3. Add `runner_pid=os.getpid()` to `start_spawn`
4. Write `exited` event after process wait returns, before finalize
5. Move harness PID recording to event stream only (already done via `mark_spawn_running`)

### `streaming_runner.py` — same changes

1. Remove `harness.pid` write (line ~425)
2. Remove `heartbeat_scope` usage
3. Add `runner_pid=os.getpid()` recording
4. Write `exited` event when connection drain completes or subprocess exits

### `execute.py:execute_spawn_background` — PID file

The `background.pid` write at line 649 is eliminated. The wrapper PID is already recorded via `mark_spawn_running(wrapper_pid=process.pid)`.

## Event Store Changes

### New event type in `spawn_store.py`

```python
class SpawnExitedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    v: int = 1
    event: Literal["exited"] = "exited"
    id: str = ""
    exit_code: int = 0
    exited_at: str | None = None

# Update SpawnEvent union:
type SpawnEvent = SpawnStartEvent | SpawnUpdateEvent | SpawnExitedEvent | SpawnFinalizeEvent

# Update _parse_event:
def _parse_event(payload: dict[str, Any]) -> SpawnEvent | None:
    event_type = payload.get("event")
    # ... existing cases ...
    if event_type == "exited":
        return SpawnExitedEvent.model_validate(payload)
    return None
```

### New fields on SpawnStartEvent

```python
class SpawnStartEvent(BaseModel):
    # ... existing fields ...
    runner_pid: int | None = None  # PID of the process that will finalize
```

### New fields on SpawnUpdateEvent

```python
class SpawnUpdateEvent(BaseModel):
    # ... existing fields ...
    runner_pid: int | None = None  # can be set via update if not known at start
```

### New fields on SpawnRecord

```python
class SpawnRecord(BaseModel):
    # ... existing fields ...
    runner_pid: int | None          # PID of the finalizing process
    exited_at: str | None           # from exited event
    process_exit_code: int | None   # raw exit code from exited event
```

### `record_spawn_exited` function

```python
def record_spawn_exited(
    state_root: Path,
    spawn_id: SpawnId | str,
    *,
    exit_code: int,
    exited_at: str | None = None,
) -> None:
    """Append an exited event — the harness process has exited."""
    paths = StateRootPaths.from_root_dir(state_root)
    event = SpawnExitedEvent(
        id=str(spawn_id),
        exit_code=exit_code,
        exited_at=exited_at or utc_now_iso(),
    )
    append_event(
        paths.spawns_jsonl,
        paths.spawns_flock,
        event,
        store_name="spawn",
        exclude_none=True,
    )
```

### `_record_from_events` update

In the projection loop, handle `SpawnExitedEvent`:

```python
if isinstance(event, SpawnExitedEvent):
    records[spawn_id] = current.model_copy(
        update={
            "exited_at": event.exited_at if event.exited_at is not None else current.exited_at,
            "process_exit_code": event.exit_code if event.exit_code is not None else current.process_exit_code,
        }
    )
    continue
```

### `cleanup_terminal_spawn_runtime_artifacts` — removal

This function removes `harness.pid`, `heartbeat`, and `background.pid`. With no runtime files, it becomes a no-op. Remove the function and all call sites.

## Heartbeat Module Elimination

### `heartbeat.py`

The entire `heartbeat.py` module can be deleted. No callers remain after runner.py, streaming_runner.py, and process.py stop using it.

### Staleness detection

The reaper's `_spawn_is_stale()` and `_recent_spawn_activity()` are eliminated. Staleness detection was a proxy for "is the process still doing work?" — `exited` event answers that definitively.

## Spawn Directory Layout

### Before

```
.meridian/spawns/p42/
  prompt.md              # durable artifact
  output.jsonl           # durable artifact
  stderr.log             # durable artifact
  report.md              # durable artifact
  params.json            # durable artifact
  tokens.json            # durable artifact (when present)
  harness.pid            # RUNTIME — eliminated
  background.pid         # RUNTIME — eliminated
  heartbeat              # RUNTIME — eliminated
  bg-worker-params.json  # launch params — kept (consumed once at startup)
```

### After

```
.meridian/spawns/p42/
  prompt.md
  output.jsonl
  stderr.log
  report.md
  params.json
  tokens.json
  bg-worker-params.json  # background spawns only
```

All runtime coordination lives in the event stream. Spawn directories are artifact-only.

## Display Layer Changes

### `spawn show`

When `record.exited_at is not None` and `record.status == "running"`:

```
Status:  running (exited 0, awaiting finalization)
```

### `spawn list`

Running spawns with `exited_at` set get a visual indicator in the status column:

```
p42  claude-opus-4  running*  Implement auth middleware
                          ^ asterisk indicates post-exit finalization
```

### `spawn wait`

No behavioral change — waits for `finalize` event (terminal status). The `exited_at` enrichment provides better diagnostics if the wait is interrupted.

## No Backward Compatibility

No legacy fallback paths. The reaper assumes all active spawns have `runner_pid` and will emit `exited` events. Old `spawns.jsonl` can be wiped on upgrade. This eliminates the `_reconcile_pre_exit` legacy path and simplifies the reaper to ~30 lines.

## Error Taxonomy

| Error code | Meaning | When |
|---|---|---|
| `orphan_run` | Harness and runner dead, no exited event, no report | Crash before any exit processing |
| `orphan_finalization` | Runner dead after exited event, no report | Crash during post-exit finalization |
| `missing_worker_pid` | No PID recorded, startup grace elapsed | Launch failure |
| `missing_spawn_dir` | Retained for startup-phase orphans | Launch failure |

`orphan_stale_harness` is eliminated — staleness detection is removed entirely.

## Files Changed

### New files
- `src/meridian/lib/state/liveness.py` — psutil liveness module (~20 lines)

### Major changes
- `src/meridian/lib/state/reaper.py` — rewritten from 500 lines to ~60 lines
- `src/meridian/lib/state/spawn_store.py` — new `SpawnExitedEvent`, `record_spawn_exited()`, updated projection, new SpawnRecord fields, removed `cleanup_terminal_spawn_runtime_artifacts`
- `src/meridian/lib/launch/runner.py` — add `exited` event write, remove heartbeat, remove harness.pid write, add runner_pid recording
- `src/meridian/lib/launch/process.py` — same changes as runner.py
- `src/meridian/lib/launch/streaming_runner.py` — same changes as runner.py

### Removed files
- `src/meridian/lib/launch/heartbeat.py` — entire module deleted

### Minor changes
- `src/meridian/lib/core/domain.py` — no changes needed (SpawnStatus unchanged)
- `src/meridian/lib/core/spawn_lifecycle.py` — no changes needed (terminal state logic unchanged)
- `src/meridian/lib/ops/spawn/execute.py` — remove `background.pid` write, update `mark_spawn_running` call
- `src/meridian/lib/ops/spawn/query.py` — update `detail_from_row` to pass `exited_at` info to display
- CLI display formatters — add post-exit display annotation
- `pyproject.toml` — add `psutil` dependency

### Call site cleanup
- All imports of `heartbeat_scope` / `threaded_heartbeat_scope` — removed
- All imports/calls of `cleanup_terminal_spawn_runtime_artifacts` — removed
- `_TERMINAL_RUNTIME_ARTIFACTS` constant — removed
