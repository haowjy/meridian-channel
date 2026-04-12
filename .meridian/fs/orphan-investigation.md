# orphan_run false-failure investigation

## Summary

Tracked issue: `meridian-flow/meridian-cli#14` ("Bug: reaper can stamp orphan_run during post-exit pipe drain")

`p1579` was marked `failed / orphan_run` by read-path reconciliation before its normal runner path finished finalization. The persisted event stream shows:

- `start` at `2026-04-12T13:32:11Z`
- `finalize failed / orphan_run` at `2026-04-12T13:34:06Z`
- `finalize succeeded` at `2026-04-12T13:48:42Z`

The later success did not repair the earlier failure because spawn projection is **first-terminal-event-wins**.

The durable report predicate is not the bug. `p1579/report.md` is plain markdown and matches `has_durable_report_completion()` immediately once it exists. The failure is the reaper deciding the spawn was orphaned during the runner's post-exit drain/finalization window, before `report.md` had been written.

## Current reaper logic

The old 500-line state machine was replaced by a single `reconcile_active_spawn()` function (~60 lines) in `src/meridian/lib/state/reaper.py`. The rearchitecture that fixed p1579 eliminated PID files, heartbeat checks, launch-mode dispatch, and staleness heuristics entirely.

`reconcile_active_spawn(state_root, record)` checks one active spawn:

1. **No runner_pid or invalid**: if within startup grace (15s of `started_at`) → wait; otherwise → `missing_worker_pid`.

2. **`is_process_alive(runner_pid, created_after_epoch=started_epoch)` returns true**: runner is still up — keep running.

3. **runner_pid dead, `exited_at` is None** (no exited event recorded): runner died before harness even exited.
   - If startup grace active → wait.
   - If durable report present → finalize succeeded.
   - Otherwise → `orphan_run`.

4. **runner_pid dead, `exited_at` is set**: harness exited (exited event recorded), runner died during post-exit finalization (pipe drain, report extraction, artifact persistence).
   - If durable report present → finalize succeeded.
   - Otherwise → `orphan_finalization`.

`liveness.py:is_process_alive(pid, created_after_epoch)` uses psutil for cross-platform liveness with PID-reuse detection via `proc.create_time()`.

### Error codes

| Error code | Meaning |
|---|---|
| `orphan_run` | Runner and harness both dead, no exited event, no report — crash before any exit processing |
| `orphan_finalization` | Runner dead after exited event, no report — crash during post-exit finalization |
| `missing_worker_pid` | No runner_pid recorded, startup grace elapsed — launch failure |

`orphan_stale_harness` no longer exists — staleness detection via heartbeat was eliminated entirely. No heartbeat files are written.

## Why `p1579` matched the report predicate

`has_durable_report_completion()` returns true for any non-empty report text that is not a terminal control frame.

It rejects only JSON payloads whose event name is `cancelled` or `error`:

- `src/meridian/lib/core/spawn_lifecycle.py:32-64`

`p1579/report.md` is:

```md
# Auto-extracted Report

Implementation complete. Both phases executed in parallel, all 11 EARS statements verified, 475 tests passing, committed as `a063ae8`.
```

That is plain markdown, so the predicate returns `true`.

The file timestamp also matches the final success event:

- `report.md` mtime: `2026-04-12 08:48:42 -0500`
- `output.jsonl` mtime: `2026-04-12 08:48:42 -0500`

That is consistent with the report being written only at the end of the real run, not at the time of the false failure.

## What actually caused the false failure

The root cause is a race between read-path reconciliation and the runner's post-exit finalization work.

The runner finalizes only after:

1. the subprocess exits,
2. stdout/stderr are drained,
3. report extraction runs,
4. `report.md` is persisted,
5. the terminal spawn record is appended.

Relevant code:

- `src/meridian/lib/launch/runner.py:288-380`
- `src/meridian/lib/launch/runner.py:823-850`
- `src/meridian/lib/launch/process.py:399-430`

The key detail is that Meridian deliberately separates "the tracked child PID exited" from "all inherited pipes are drained". `wait_for_process_returncode()` explicitly polls `process.returncode` instead of awaiting `process.wait()` because descendants may inherit stdout/stderr and keep those pipes open after the tracked PID exits:

- `src/meridian/lib/launch/timeout.py:21-46`
- `src/meridian/lib/launch/runner.py:346-399`

That means this state is expected and supported:

- the harness PID (recorded in spawn events) is dead
- the runner is still alive
- stdout/stderr drain tasks are still in progress
- `report.md` does not exist yet
- final `finalize_spawn(...)` has not happened yet

The reaper has no notion of "finalization in progress". Once it sees:

- no durable report yet, and
- dead harness / wrapper, and
- grace elapsed,

it stamps `orphan_run` immediately.

That is exactly the hole that hit `p1579`: the tracked foreground PID was already dead, but the authoritative runner path was still draining output and had not yet persisted the report.

### Why the later success could not repair it

`spawn_store._record_from_events()` is explicitly first-terminal-event-wins:

- once a record is terminal, later finalize events cannot change `status`, `exit_code`, or `error`

Relevant code:

- `src/meridian/lib/state/spawn_store.py:468-518`

So the later `succeeded` event from the runner was appended, but the projection kept the earlier `failed / orphan_run` terminal state.

That is why `meridian spawn show` kept reporting the failure even though the successful finalize event exists in `spawns.jsonl`.

## p1579 timeline

The persisted events for `p1579` show:

- `start` at `7802`
- `running` update at `7805`
- `failed / orphan_run` at `7812`
- `harness_session_id` update at `7843`
- `succeeded` finalize at `7844`

Relevant file:

- `.meridian/spawns.jsonl:7802-7844`

Important detail: the stored launch mode on the start event is `foreground`, even though the task prompt described the run as background-oriented. So the foreground reconcile path is the one that actually misclassified this spawn record.

## Is issue #10 the same root cause?

Issue #10 says: "`meridian --json spawn wait <id>` returns `succeeded`, but a subsequent `meridian spawn show <id>` still reports `running` even though `finished_at` is populated."

Current code paths:

- `spawn_wait_sync()` polls `read_spawn_row()` until it sees a terminal row
- `spawn_show_sync()` also reads the row through `read_spawn_row()`
- `read_spawn_row()` runs the same read-path reconciliation for active rows

Relevant code:

- `src/meridian/lib/ops/spawn/api.py:615-682`
- `src/meridian/lib/ops/spawn/query.py:67-73`

So in the current tree, `wait` and `show` are supposed to converge on the same persisted row state.

My conclusion:

- Same family: yes. Both are state-reporting inconsistencies around terminalization/reconciliation timing.
- Same exact root cause: not proven, and probably not. `p1579` is specifically a premature `orphan_run` finalize during post-exit pipe drain. Issue #10 describes the opposite polarity: a row that stayed active after a terminal result had already been observed.

In other words, both bugs point at lifecycle ambiguity around finalization, but `p1579` gives a concrete root cause that is narrower than the symptom reported in #10.

## Resolution

The rearchitecture that landed after this investigation fixed the root cause directly rather than patching the old state machine. Key changes:

**`exited` event in the spawn stream**: `runner.py` and `process.py` now write `record_spawn_exited()` immediately after the harness process exits, before pipe drain or report extraction. The `exited_at` field on `SpawnRecord` tells the reaper: “harness is done, runner is still working.” The `exited` event does NOT change the spawn's `status` — the spawn stays `running` until `finalize`.

**runner_pid in start event**: The `runner_pid` field in the spawn start event records the PID of the process responsible for finalization. The reaper checks this PID (not the harness/child PID) via psutil, eliminating the ambiguous “dead child but parent still cleaning up” window that caused p1579.

**Simplified reaper**: The old 500-line state machine with background/foreground/legacy paths, PID file inspection, and heartbeat staleness checks was replaced by a single ~60-line function (see “Current reaper logic” above). The `orphan_stale_harness` error code is gone. `orphan_finalization` distinguishes “runner crashed during post-exit work” from `orphan_run` (crash before any exit processing).

**Heartbeat eliminated**: `heartbeat.py` was deleted. No heartbeat files are written. Staleness detection via filesystem timestamps is gone. The `exited` event + psutil liveness is definitive.

**Spawn directories artifact-only**: `harness.pid`, `background.pid`, and `heartbeat` files no longer exist. All runtime coordination lives in `spawns.jsonl`. Spawn directories contain only durable artifacts (`output.jsonl`, `stderr.log`, `report.md`, `tokens.json`, `params.json`).

The first-terminal-event-wins invariant is preserved. The fix works by preventing the reaper from issuing a premature terminal event in the first place — not by weakening the projection model.

## Bottom line

`p1579` was not a bad report parse. It was a lifecycle race.

The reaper finalized `orphan_run` while the runner was still finishing post-exit work, and the later success could not override the first terminal event in the event log.

The real fix is to model finalization explicitly instead of inferring failure from a dead child plus a missing report.
