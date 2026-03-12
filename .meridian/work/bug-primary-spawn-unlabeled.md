# Primary Spawn Missing Work Association and Label

## Summary

This is not one bug; it is two separate propagation gaps in two different state systems:

1. The primary spawn is created through the primary launch path, not the child spawn path, so it never gets the child path's `work_id` or `desc` wiring.
2. Later `work start` / `work switch` commands update the session's `active_work_id`, but dashboards group by `spawn.work_id`, not by session state, and spawn update events cannot currently backfill `work_id` or `desc`.

That combination explains the observed behavior:

- the primary/orchestrator spawn lands in `spawns.jsonl` with `kind="primary"` but no `work_id` and no `desc`
- `meridian work` groups only on `spawn.work_id`, so the primary falls under `(no work)`
- the dashboard label renderer only uses `spawn.desc`, so the primary has no visible label even though `kind` is already stored
- child spawns look correct because they go through `_init_spawn()`, which resolves and persists `work_id` and `desc`

## Trace

### 1. How the primary spawn is created

The primary path is `cli/main.py` -> `launch_primary()` -> `run_harness_process()`.

- [`src/meridian/cli/main.py:523`](/home/jimyao/gitrepos/meridian-channel/src/meridian/cli/main.py#L523) builds a `LaunchRequest`.
- [`src/meridian/lib/launch/types.py:15`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/types.py#L15) shows `LaunchRequest` has no `work_id`, no `desc`, and no primary-role label field.
- [`src/meridian/lib/launch/process.py:424`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/process.py#L424) starts the Meridian session.
- [`src/meridian/lib/launch/process.py:435`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/process.py#L435) creates the primary spawn with:
  - `kind="primary"`
  - `prompt=ctx.prompt`
  - `launch_mode="foreground"`
  - `status="queued"`
  - but no `work_id`
  - and no `desc`

So the primary spawn record is born unlabeled and unassociated.

### 2. Why launch-time work context does not get injected

The primary launch env does carry runtime context, but only from the caller's current environment:

- [`src/meridian/lib/launch/command.py:271`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/command.py#L271) reads `RuntimeContext.from_environment()`
- [`src/meridian/lib/launch/command.py:280`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/command.py#L280) sets the primary harness env's `work_id` to `current_context.work_id`

That means the primary launch can only inherit `MERIDIAN_WORK_ID` if the parent process already had it in its environment. The primary launch path does not consult tracked session state for `active_work_id`, and it does not accept an explicit `work_id` in `LaunchRequest`.

### 3. How child spawns get their `work_id`

Child spawns go through `_init_spawn()` instead:

- [`src/meridian/lib/ops/spawn/execute.py:348`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/spawn/execute.py#L348) resolves `work_id` from:
  - explicit `--work`, or
  - inherited `runtime_context.work_id`
- [`src/meridian/lib/ops/spawn/execute.py:379`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/spawn/execute.py#L379) persists that `work_id`
- [`src/meridian/lib/ops/spawn/execute.py:379`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/spawn/execute.py#L379) also persists `desc`

So child spawns have the metadata that the dashboards expect.

### 4. What the active work item context actually is

The durable "active work item" lives on the session record, not on the spawn record:

- [`src/meridian/lib/state/session_store.py:20`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/state/session_store.py#L20) defines `SessionRecord.active_work_id`
- [`src/meridian/lib/state/session_store.py:289`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/state/session_store.py#L289) updates it via `update_session_work_id()`
- [`src/meridian/lib/ops/work.py:363`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L363) and [`src/meridian/lib/ops/work.py:453`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L453) call that updater from `work start` and `work switch`

But the dashboards do not group by session state:

- [`src/meridian/lib/ops/work.py:331`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L331) iterates spawns
- [`src/meridian/lib/ops/work.py:335`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L335) groups only when `spawn.work_id` is populated

So once a primary spawn is created without `work_id`, later session-level work changes do not move it out of `(no work)`.

### 5. Why the primary has no label

The label gap is separate from the work gap.

- [`src/meridian/lib/state/spawn_store.py:92`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/state/spawn_store.py#L92) already stores `kind`
- the primary path sets `kind="primary"` at [`src/meridian/lib/launch/process.py:441`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/process.py#L441)
- but [`src/meridian/lib/ops/work.py:42`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L42) renders only `spawn.desc`

If `desc` is empty, the dashboard shows an empty label even though `kind` already tells us this is the primary orchestrator.

### 6. Why this cannot currently be backfilled cleanly

`spawn_store` update events do not support metadata updates:

- [`src/meridian/lib/state/spawn_store.py:132`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/state/spawn_store.py#L132) allows only status / launch mode / PIDs / error on update

So even when `work start` or `work switch` changes the session's active work item, there is no supported way to patch the existing primary spawn's `work_id` or `desc`.

## Root Cause

The primary launch path and the child spawn path evolved separately.

Child spawns have a complete metadata path:

- resolve work context
- persist `work_id`
- persist `desc`
- propagate env to nested runs

Primary spawns only have lifecycle tracking:

- start session
- append primary spawn start event
- launch harness
- finalize

No code bridges session work state into the primary spawn record, and no renderer falls back to `kind` for label display.

## Concrete Fix

I would fix this in three layers, not just in the dashboard.

### A. Add launch-time work propagation for the primary path

Add `work_id: str | None = None` to `LaunchRequest`.

When building the request in [`src/meridian/cli/main.py`](/home/jimyao/gitrepos/meridian-channel/src/meridian/cli/main.py):

- keep supporting inherited `MERIDIAN_WORK_ID` from `RuntimeContext`
- when `--continue` resolves to an existing Meridian session, also load that session's `active_work_id`
- prefer an explicit request work id if one is later exposed as a CLI flag

Then in [`src/meridian/lib/launch/process.py:435`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/process.py#L435):

- pass `work_id=resolved_primary_work_id` to `spawn_store.start_spawn()`

And in [`src/meridian/lib/launch/command.py:262`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/launch/command.py#L262):

- pass that same resolved work id into `build_launch_env()` instead of relying only on `RuntimeContext.from_environment()`

This makes resumed or already-scoped primary launches inherit work context immediately, and it also lets child spawns inherit `MERIDIAN_WORK_ID` from the primary process without always needing explicit `--work`.

### B. Backfill the running primary spawn when work changes after launch

This is the part that actually matches the observed bug most closely.

After `work start` / `work switch` updates `session.active_work_id`, also update the active primary spawn for the same `chat_id`.

That requires extending spawn metadata updates:

- add optional `work_id` and `desc` fields to `SpawnUpdateEvent`
- extend `update_spawn()` or add a dedicated `update_spawn_metadata()`
- teach `_record_from_events()` to merge those fields just like it already merges status/PID/error

Then in [`src/meridian/lib/ops/work.py:363`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L363) and [`src/meridian/lib/ops/work.py:453`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L453):

- after `_set_active_work_id(...)`, find the active `kind="primary"` spawn for that `chat_id`
- write `work_id=item.name` onto that spawn

Without this step, launch-time propagation alone will still miss the common case where the primary session starts first and the work item is chosen later.

### C. Fix the missing label at the renderer level

Do not rely solely on persisted `desc` for the primary label.

Change [`src/meridian/lib/ops/work.py:42`](/home/jimyao/gitrepos/meridian-channel/src/meridian/lib/ops/work.py#L42) so that:

- if `spawn.desc` is present, render it
- else if `spawn.kind == "primary"`, render `(primary)` or `primary orchestrator`

This uses data the store already has and makes the UI robust even for older records created before the metadata fix.

I would still allow the spawn record itself to carry a standardized desc for primary spawns, but the renderer fallback is the safer fix because it handles pre-existing rows.

## Recommended Implementation Shape

1. Add a small helper in `session_store` to read a session by `chat_id` or directly return `active_work_id`.
2. Extend `LaunchRequest` and `build_launch_env()` to accept an explicit resolved primary `work_id`.
3. Extend spawn update events to allow metadata backfill (`work_id`, optionally `desc`).
4. Add a helper in `ops/work.py` that annotates the current primary spawn for a session after `work start` / `work switch`.
5. Add a dashboard desc fallback based on `spawn.kind`.

## What I Would Not Do

I would not solve this only in the dashboard by dynamically joining `primary spawn.chat_id` to `session.active_work_id`.

That would make `meridian work` look better, but:

- `spawn.work_id` would still be wrong on disk
- `work show` filters by stored `spawn.work_id`, so it would stay inconsistent
- any other consumer of `spawns.jsonl` would still see an orphan

The durable fix is to write the association onto the spawn record and use UI fallback for the label.

## Verification To Add

I did not run tests; this was code-path inspection only.

After implementation, I would add:

1. A test where a primary session starts with no work, then `work start` is called, and the active primary spawn moves under that work item.
2. A test where `work switch` changes the active work item and the active primary spawn is re-associated.
3. A test where a resumed primary launch inherits an existing session `active_work_id`.
4. A dashboard rendering test that shows `(primary)` when `kind="primary"` and `desc` is empty.
