# Spawn Store

Source: `src/meridian/lib/state/spawn_store.py`, `src/meridian/lib/state/reaper.py`

## Event Model

Spawns are tracked as an append-only event sequence in `.meridian/spawns.jsonl`. Three event types:

**`start`** — written when spawn is created. Fields include:
- `id` (e.g. `p1`, `p2`), `chat_id`, `parent_id`
- `model`, `agent`, `agent_path`, `skills`, `skill_paths`, `harness`
- `kind` (`"child"` or `"primary"`), `desc`, `work_id`
- `harness_session_id`, `execution_cwd`, `launch_mode`
- `worker_pid`, `status` (initial: `"running"` or `"queued"`), `prompt`, `started_at`

**`update`** — non-terminal state change. Fields: `id`, `status`, `launch_mode`, `wrapper_pid`, `worker_pid`, `harness_session_id`, `execution_cwd`, `error`, `desc`, `work_id`.

**`finalize`** — terminal event. Fields: `id`, `status`, `exit_code`, `finished_at`, `duration_secs`, `total_cost_usd`, `input_tokens`, `output_tokens`, `error`.

`SpawnRecord` is the projection: derived by replaying all events for a spawn ID.

## ID Generation

`next_spawn_id()` counts `start` events in `spawns.jsonl` and returns `p{count+1}`. IDs are sequential and monotonic. Allocation happens under the spawns flock so concurrent spawners don't collide.

## Terminal Status Merging

`finalize_spawn()` uses asymmetric merging when multiple finalize events exist for the same spawn (e.g., reaper and primary process both finalize concurrently):

- `succeeded` wins over all other terminal statuses
- For non-success states: the **first** terminal status (lowest event index) wins

Rationale: a spawn that succeeded shouldn't be retroactively marked failed because the reaper raced to finalize it. But for non-success states, the first reporter has the most accurate original reason.

`finalize_spawn()` always appends the event even if the spawn is already terminal — this ensures cost/token metadata isn't lost. Returns `True` if this call moved the spawn from active → terminal, `False` if already terminal.

## Spawn Statuses

Active: `queued`, `running`
Terminal: `succeeded`, `failed`, `cancelled`, `timeout`

## Reaper (`reaper.py`)

The reaper runs on every read path (`spawn list`, `spawn show`, `spawn wait`, dashboard). It auto-repairs active spawns that have become orphaned. No separate GC command.

**Orphan detection logic** (in priority order):
1. **Missing PID file + outside startup grace (15s):** finalize as `failed`
2. **PID dead (checked via `os.kill(pid, 0)`):** check for durable report → `succeeded`; else `failed`
3. **Stale output (no output file mtime update in 300s):** same as dead PID
4. **Durable report present (`report.md` exists):** finalize as `succeeded` regardless of PID state
5. **PID alive:** update to `running` if still queued, leave alone

PID reuse guard (Linux): reads `/proc/<pid>/stat` start time and compares against system boot time to detect if a new process grabbed the same PID.

**Startup grace window:** 15 seconds after `started_at` before the reaper considers a missing PID file an error. This covers the window between `start_spawn()` and the runner writing `harness.pid`.

**Stale threshold:** 300 seconds (5 minutes) without output file mtime update.

## Artifact Directory

Each spawn gets `.meridian/spawns/<id>/` containing:
- `prompt.md` — the prompt text
- `report.md` — the agent's run report (explicit or auto-extracted)
- `output.jsonl` — raw harness stdout (JSON stream events)
- `harness.pid` — harness process PID
- `heartbeat` — touched periodically by the heartbeat writer
- Additional harness-specific files as needed

`spawn files` returns the list of files a spawn created/modified, for use with `xargs git add`.
