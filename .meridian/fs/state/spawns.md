# Spawn Store

Source: `src/meridian/lib/state/spawn_store.py`, `src/meridian/lib/state/reaper.py`, `src/meridian/lib/state/liveness.py`

## Event Model

Spawns are tracked as an append-only event sequence in `.meridian/spawns.jsonl`. Four event types:

**`start`** — written when spawn is created. Fields include:
- `id` (e.g. `p1`, `p2`), `chat_id`, `parent_id`
- `model`, `agent`, `agent_path`, `skills`, `skill_paths`, `harness`
- `kind` (`"child"` or `"primary"`), `desc`, `work_id`
- `harness_session_id`, `execution_cwd`, `launch_mode`
- `worker_pid`, `runner_pid`, `status` (initial: `"running"` or `"queued"`), `prompt`, `started_at`

`runner_pid` on the start event identifies the foreground/primary runner — the process responsible for post-exit finalization. For foreground spawns this is `os.getpid()` at launch time.

**`update`** — non-terminal state change. Fields: `id`, `status`, `launch_mode`, `wrapper_pid`, `worker_pid`, `runner_pid`, `harness_session_id`, `execution_cwd`, `error`, `desc`, `work_id`.

`runner_pid` on the update event is used for background spawns: the wrapper process PID is recorded here once the background launch stabilizes.

**`exited`** — written immediately when the harness process exits (before report extraction or any post-exit work). Fields: `id`, `exit_code`, `exited_at` (ISO 8601 UTC).

This event is **informational, not terminal**. The spawn status stays `running` after an `exited` event — the runner is still draining pipes, extracting reports, and persisting artifacts. The event is a lifecycle marker the reaper uses to distinguish "runner is finalizing" from "runner hasn't done anything yet." (Decision D9: making `exited` terminal would create a window where spawns appear "done" but lack report data.)

**`finalize`** — terminal event. Fields: `id`, `status`, `exit_code`, `finished_at`, `duration_secs`, `total_cost_usd`, `input_tokens`, `output_tokens`, `error`.

`SpawnRecord` is the projection: derived by replaying all events for a spawn ID.

## ID Generation

`next_spawn_id()` counts `start` events in `spawns.jsonl` and returns `p{count+1}`. IDs are sequential and monotonic. Allocation happens under the spawns flock so concurrent spawners don't collide.

## SpawnRecord

`SpawnRecord` is the projection: assembled from all events for a spawn. Key fields:

- `runner_pid` — PID of the process responsible for finalization (sourced from start or update event)
- `exited_at` — timestamp from the `exited` event (None if harness hasn't exited yet)
- `process_exit_code` — raw exit code from the `exited` event (distinct from the `exit_code` in the finalize event, which is the final outcome code)
- All other fields follow from start/update/finalize events

## Terminal Status Merging

`finalize_spawn()` uses asymmetric merging when multiple finalize events exist for the same spawn (e.g., reaper and primary process both finalize concurrently):

- `succeeded` wins over all other terminal statuses
- For non-success states: the **first** terminal status (lowest event index) wins

Rationale: a spawn that succeeded shouldn't be retroactively marked failed because the reaper raced to finalize it. But for non-success states, the first reporter has the most accurate original reason.

`finalize_spawn()` always appends the event even if the spawn is already terminal — this ensures cost/token metadata isn't lost. Returns `True` if this call moved the spawn from active → terminal, `False` if already terminal.

## Spawn Statuses

Active: `queued`, `running`
Terminal: `succeeded`, `failed`, `cancelled`

There is no `timeout` status. Timeouts result in `failed` status with a timeout-related failure reason.

Presence of an `exited` event does **not** change the spawn's projected status. The spawn stays `running` until a `finalize` event arrives. This means `spawn wait` blocks until finalize, not exited.

## Reaper (`reaper.py`)

The reaper runs on every read path (`spawn list`, `spawn show`, `spawn wait`, dashboard). It auto-repairs active spawns that have become orphaned. No separate GC command.

**Core logic** (`reconcile_active_spawn`):

1. If `runner_pid` is absent or ≤ 0:
   - Within startup grace window (15s from `started_at`): leave alone
   - Otherwise: finalize as `failed` with error `missing_worker_pid`

2. Check `runner_pid` liveness via `is_process_alive()`:
   - **Alive**: leave alone (still working)
   - **Dead**: proceed to step 3

3. Select orphan reason based on `exited_at` presence:
   - `exited_at` is None → `orphan_run` (runner died before harness even exited)
   - `exited_at` is set → `orphan_finalization` (harness exited, runner died during post-exit work)

4. If dead runner + no `exited_at` + within startup grace: leave alone (covers the brief gap between `start_spawn()` and the runner establishing its PID)

5. Check for durable report (`report.md` with content):
   - Present: finalize as `succeeded` (work completed before crash)
   - Absent: finalize as `failed` with the orphan reason from step 3

**Error codes:**
- `orphan_run` — runner died before the harness exited. Neither harness nor runner survived. Suggests a hard kill or OOM.
- `orphan_finalization` — harness exited cleanly, but runner died during post-exit processing (report extraction, artifact persistence). Rarer; suggests infrastructure issues, not harness problems. (Decision D15)
- `missing_worker_pid` — no `runner_pid` recorded and outside startup grace. Spawn started but PID was never committed to the event stream.

**Startup grace window:** 15 seconds after `started_at`. Applied to spawns with no `exited` event where the runner PID hasn't been recorded yet. This is the only timing heuristic — no staleness thresholds, no heartbeat checks.

## Liveness (`liveness.py`)

`is_process_alive(pid, created_after_epoch)` — psutil-based, cross-platform process liveness check.

- Uses `psutil.pid_exists()` for fast path.
- Retrieves `psutil.Process(pid).create_time()` to guard against PID reuse: if the process was created more than 2 seconds after `created_after_epoch` (the spawn's `started_at` epoch), it's a different process that reused the PID.
- Returns `True` on `psutil.AccessDenied` (process exists, can't inspect — conservatively assume alive).
- Returns `False` on `psutil.NoSuchProcess` (process vanished between `pid_exists` and `Process(pid)` — treat as dead).

Replaces the prior Linux-only `/proc/stat` boot time + clock tick approach. Decision D10: psutil chosen for cross-platform support and built-in `create_time()` PID-reuse detection with no transitive dependencies.

## Artifact Directory

Each spawn gets `.meridian/spawns/<id>/` containing only durable artifacts (Decision D13: no PID files, heartbeat files, or coordination signals in spawn dirs — the event stream is self-sufficient):

- `prompt.md` — the prompt text
- `report.md` — the agent's run report (explicit or auto-extracted)
- `output.jsonl` — raw harness stdout (JSON stream events)
- `stderr.log` — harness stderr, warnings, and errors
- `params.json` — spawn parameters
- `tokens.json` — token usage record
- `bg-worker-params.json` — background launch parameters (background spawns only)

`spawn files` returns the list of files a spawn created/modified, for use with `xargs git add`.
