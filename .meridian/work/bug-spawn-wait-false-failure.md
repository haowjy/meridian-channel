# Bug Investigation: `meridian spawn wait` false failure on successful spawns

## Summary

`spawn wait` can report a spawn as failed even when the harness ultimately finishes with `status=succeeded` and `exit_code=0`.

This is a read-path race:

1. `spawn wait` polls `read_spawn_row()`.
2. `read_spawn_row()` reconciles active spawns on the read path.
3. The reaper can append a synthetic `finalize(status="failed", error="orphan_run")` before the real runner finalization lands.
4. `spawn wait` treats that synthetic failed row as terminal and exits 1.
5. The runner later appends the real `finalize(status="succeeded", exit_code=0)`.
6. `spawn show` then reads the later succeeded state.

There is a second bug that makes the symptom more confusing: a later successful `finalize` does not clear an earlier reconciliation error, so the final row can become `succeeded` with a stale warning.

## Files traced

- `src/meridian/lib/ops/spawn/api.py`
- `src/meridian/lib/ops/spawn/query.py`
- `src/meridian/lib/state/reaper.py`
- `src/meridian/lib/state/spawn_store.py`
- `src/meridian/lib/launch/runner.py`
- `src/meridian/cli/spawn.py`

## Control flow

### 1. What happens when `spawn wait` polls a spawn that is finishing?

`spawn_wait_sync()` loops over pending IDs and calls `read_spawn_row()` for each one. If the returned row is non-active, it is treated as terminal immediately and removed from `pending`.

Relevant code:

- `spawn_wait_sync()` checks terminality and stops polling: `src/meridian/lib/ops/spawn/api.py:534-554`
- `read_spawn_row()` reconciles any active row before returning it: `src/meridian/lib/ops/spawn/query.py:66-72`

So `spawn wait` is not passively reading state. It is invoking the reaper on every poll.

### 2. How does `"harness_completed"` warning interact with status determination?

In the current branch, it does not appear to be the primary cause.

- `spawn wait` only looks at `row.status`: `src/meridian/lib/ops/spawn/api.py:540-542`
- CLI exit code is derived only from `result.any_failed`: `src/meridian/cli/spawn.py:353-366`

The exact string `"harness_completed"` only appears in `reaper.py` as the unused fallback passed to `resolve_reconciled_terminal_state()` inside `_finalize_completed_report()`: `src/meridian/lib/state/reaper.py:322-334`

Because `_finalize_completed_report()` calls `resolve_reconciled_terminal_state(durable_report_completion=True, ...)`, that path returns `("succeeded", 0, None)` and does not persist `"harness_completed"` on this branch.

I could not reproduce the exact `"harness_completed"` warning from current code. I could reproduce the more general symptom: a stale warning survives after a later successful finalize because final finalize events do not clear `error`.

### 3. Is there a race between the harness completing and the finalize event being written?

Yes.

The runner writes the authoritative finalize event only at the end of `execute_with_finalization()`: `src/meridian/lib/launch/runner.py:851-884`

Before that point, there is a window where:

- the harness process may already be gone,
- the spawn record is still `queued` or `running`,
- `report.md` may not exist yet,
- `spawn wait` may poll the row and trigger reconciliation.

That window is real because report materialization can happen during finalization, not necessarily before process exit:

- report extraction/persistence is performed by `enrich_finalize()`: `src/meridian/lib/launch/extract.py:96-124`
- `_persist_report()` may create `report.md` from fallback extraction after process exit: `src/meridian/lib/launch/extract.py:56-76`

So a spawn can be "done enough to succeed" from the runner's perspective while still looking orphaned to the reaper for a short interval.

### 4. Could the reaper be marking a completed spawn as failed before the finalize event lands?

Yes. This is the primary bug.

#### Background path

In `_reconcile_background_spawn()`, the reaper marks the spawn failed as soon as both wrapper and harness are dead:

- orphan check before report check: `src/meridian/lib/state/reaper.py:406-411`

This is the critical ordering bug for background spawns:

```python
if not inspection.wrapper_alive and not inspection.harness_alive:
    return _finalize_failed(state_root, record, "orphan_run")

if has_durable_report_completion(inspection.report_text):
    ...
```

If both processes exit before the runner appends the authoritative finalize event, `spawn wait` can observe a synthetic failed terminal state first.

#### Foreground path

Foreground is slightly safer, but still racy:

- orphan check before report check: `src/meridian/lib/state/reaper.py:451-456`

```python
if not inspection.harness_alive and inspection.grace_elapsed:
    return _finalize_failed(state_root, record, "orphan_run")

if has_durable_report_completion(inspection.report_text):
    ...
```

If the harness exits cleanly but there was no recent output and no `report.md` yet, `grace_elapsed` can already be true and the reaper can still stamp `orphan_run` before finalization persists success.

## Reproduced locally

I reproduced the state-store version of the bug with a one-off `uv run python` script:

1. Start a spawn in `running` state.
2. Create `harness.pid` pointing at a dead PID.
3. Do not create `report.md`.
4. Call `read_spawn_row()`.
5. Reconciliation finalizes the spawn as `failed/orphan_run`.
6. Append a later `finalize(status="succeeded", exit_code=0)`.
7. Reading again shows `status=succeeded, exit_code=0`, but the old `error` remains.

Observed output:

```text
after read_spawn_row: failed 1 orphan_run
after finalize_spawn: succeeded 0 orphan_run
```

That matches the reported operator experience:

- `spawn wait` exits 1 because it saw the synthetic failed state.
- `spawn show` later shows `succeeded` because the later finalize event wins on status/exit code.
- the success row can still carry a stale warning.

## Why the stale warning survives

`_record_from_events()` preserves the previous `error` whenever a finalize event omits `error`:

- finalize merge logic: `src/meridian/lib/state/spawn_store.py:478-497`

Current behavior:

```python
"error": event.error if event.error is not None else current.error,
```

So if reconciliation first appended:

- `finalize(status="failed", error="orphan_run")`

and the runner later appended:

- `finalize(status="succeeded", exit_code=0, error=None)`

the final row becomes:

- `status="succeeded"`
- `exit_code=0`
- `error="orphan_run"`  ← stale

That is a separate correctness bug.

## Proposed fix

### Fix 1: make durable completion / finalization-in-progress win over orphan detection

Minimum safe change:

1. In both `_reconcile_background_spawn()` and `_reconcile_foreground_spawn()`, check `has_durable_report_completion()` before any `orphan_run` finalization.
2. For background spawns, do not immediately fail when both processes are dead. Gate that path behind a short post-exit grace, similar to the existing startup grace.
3. For foreground spawns, keep the grace gate, but apply report-first ordering as well.

Rationale:

- If `report.md` already exists, it is authoritative and should win.
- If the process just exited and the runner is still in extraction/finalize, the reaper should not synthesize a terminal failure immediately.

Concretely:

- Move the `has_durable_report_completion(...)` block above the `orphan_run` block.
- Add a short "finalize grace" check for the dead-process path, ideally based on recent artifact activity or the PID file mtime.

### Fix 2: successful finalize events must clear stale errors

Change finalize event reduction so finalization is authoritative for `error`:

- update `src/meridian/lib/state/spawn_store.py:478-497`
- use `"error": event.error` for finalize events instead of preserving `current.error`

That makes a later successful finalize clear stale reconciliation warnings.

Given the repo guidance ("no backwards compatibility needed"), this schema behavior should be changed directly rather than worked around in presentation code.

## Recommended regression tests

1. `spawn wait` should not fail if reconciliation sees a dead process and the runner later finalizes success.
2. A later successful finalize should clear any earlier reconciliation error.
3. Background reconciliation should not emit `orphan_run` immediately when both PIDs are dead but the spawn has very recent activity.
4. Foreground reconciliation should prefer `report.md` over `orphan_run`.

## Bottom line

The false failure is not caused by `spawn wait` misreading warnings directly. The bug is that `spawn wait` polls through `read_spawn_row()`, and `read_spawn_row()` runs a reaper that can synthesize `failed/orphan_run` before the authoritative runner finalize event lands.

The stale warning on later `spawn show` is a second bug in event reduction: successful finalize events do not clear prior errors.
