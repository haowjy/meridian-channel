# Phase 3: Thread `source_execution_cwd` from Reference Resolver to Launch Sites

## Scope

Add `source_execution_cwd` to the continuation DTOs so Phase 4 can use it to create session symlinks. Thanks to Phase 2b's consolidation, the field is added to only 2 DTOs (`ResolvedSessionReference` and `SessionContinuation`) and flows automatically through both paths. Thanks to Phase 1c's background worker persistence, no argv serialization is needed.

Two paths carry the value:
1. **Spawn command path** (child spawns): resolver -> `SpawnCreateInput.session` -> `PreparedSpawnPlan.session` -> execute.py -> runner.py
2. **Primary launch path** (root --fork): resolver -> `LaunchRequest.session` -> `ResolvedPrimaryLaunchPlan` -> process.py

Both paths originate from `resolve_session_reference()` which reads `execution_cwd` from spawn/session records (written by Phase 2a).

## Files to Modify

### `src/meridian/lib/ops/reference.py`

1. **`ResolvedSessionReference`**: Add field `source_execution_cwd: str | None = None`.

2. **`_build_tracked_reference()`** (from Phase 1d): Add parameter `source_execution_cwd: str | None = None`. Pass it to the returned `ResolvedSessionReference`.

3. **`_resolve_spawn_reference()`**: Pass `source_execution_cwd=row.execution_cwd` to `_build_tracked_reference()`.

4. **`_resolve_chat_reference()`**: Pass `source_execution_cwd=session.execution_cwd` to `_build_tracked_reference()`.

5. **`_resolve_harness_session_reference()`**: Pass `source_execution_cwd=session.execution_cwd` to `_build_tracked_reference()`.

6. **`_resolve_untracked_reference()`**: No change -- `source_execution_cwd` defaults to `None` (untracked sessions have no recorded CWD).

### `src/meridian/lib/ops/spawn/plan.py`

1. **`SessionContinuation`**: Add field `source_execution_cwd: str | None = None`.

That's it. The field automatically flows through `PreparedSpawnPlan.session` to the launch sites. And thanks to Phase 1c, the background worker path automatically persists/loads it via `BackgroundWorkerParams` (which embeds the continuation fields -- add `source_execution_cwd` to `BackgroundWorkerParams` too).

### `src/meridian/lib/ops/spawn/execute.py`

1. **`BackgroundWorkerParams`** (from Phase 1c): Add field `source_execution_cwd: str | None = None`. This automatically flows through disk persistence.

2. **`execute_spawn_background()`**: Include `source_execution_cwd=prepared.session.source_execution_cwd` when constructing `BackgroundWorkerParams`.

3. **`_execute_existing_spawn()`**: Add parameter `source_execution_cwd: str | None = None`. Pass to `SessionContinuation(source_execution_cwd=source_execution_cwd, ...)` in the plan construction.

4. **`_background_worker_main()`**: Pass `source_execution_cwd=params.source_execution_cwd` to `_execute_existing_spawn()`.

### `src/meridian/cli/spawn.py`

1. **Fork path** (~line 270): Add `source_execution_cwd=resolved_reference.source_execution_cwd` to the `SessionContinuation` inside `SpawnCreateInput.session`:
   ```python
   session=SessionContinuation(
       harness_session_id=resolved_reference.harness_session_id,
       continue_fork=True,
       forked_from_chat_id=resolved_reference.source_chat_id,
       source_execution_cwd=resolved_reference.source_execution_cwd,
   ),
   ```

### `src/meridian/cli/main.py`

1. **Fork path**: Add `source_execution_cwd=resolved_fork.source_execution_cwd` to the `SessionContinuation` inside `LaunchRequest.session`:
   ```python
   session=SessionContinuation(
       harness_session_id=continue_harness_session_id,
       continue_fork=continue_fork,
       forked_from_chat_id=forked_from_chat_id,
       source_execution_cwd=resolved_fork.source_execution_cwd,
   ),
   ```

   Note: `resolved_fork` comes from `_resolve_session_target()` which calls `resolve_session_reference()`. Update `_ResolvedSessionTarget` to carry `source_execution_cwd`:

2. **`_ResolvedSessionTarget`**: Add field `source_execution_cwd: str | None = None`.

3. **`_resolve_session_target()`**: Pass `source_execution_cwd=resolved.source_execution_cwd` when constructing `_ResolvedSessionTarget`.

### `src/meridian/lib/launch/types.py`

No changes needed if `LaunchRequest.session` already carries `source_execution_cwd` via `SessionContinuation` from Phase 2b. The field flows through `session`.

### `src/meridian/lib/launch/plan.py`

1. **`ResolvedPrimaryLaunchPlan`**: Add field `source_execution_cwd: str | None = None`.

2. **`resolve_primary_launch_plan()`**: Populate from request:
   ```python
   source_execution_cwd=request.session.source_execution_cwd,
   ```

### `src/meridian/lib/ops/spawn/prepare.py`

1. **`build_create_payload()`**: Thread `source_execution_cwd` from the input's session field to the output's SessionContinuation:
   ```python
   session=SessionContinuation(
       harness_session_id=resolved_continue_harness_session_id,
       continue_fork=resolved_continue_fork,
       forked_from_chat_id=resolved_forked_from,
       source_execution_cwd=payload.session.source_execution_cwd,
   ),
   ```

## Dependencies

- **Requires**: Phase 2a (`execution_cwd` on records so resolver can read it), Phase 2b (consolidated `SessionContinuation` DTO), Phase 1c (BackgroundWorkerParams model)
- **Produces**: `source_execution_cwd` available at both launch sites. Phase 4 consumes these.

## Interface Contract

```python
@dataclass(frozen=True)
class ResolvedSessionReference:
    ...
    source_execution_cwd: str | None = None

class SessionContinuation(BaseModel):
    ...
    source_execution_cwd: str | None = None

class ResolvedPrimaryLaunchPlan(BaseModel):
    ...
    source_execution_cwd: str | None = None
```

## Constraints

- All new fields default to `None` for backward compatibility.
- `source_execution_cwd` is the CWD where the **source** session was created (the one being forked/resumed from). Distinct from `execution_cwd` (where the **current** spawn runs).
- Do NOT implement symlink logic or call `_ensure_claude_session_accessible()` -- that's Phase 4.
- Thanks to Phase 1c, no argv serialization changes are needed for the background worker. The field is in `BackgroundWorkerParams` and auto-persisted.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] Trace (spawn path): `resolve_session_reference()` -> `ResolvedSessionReference.source_execution_cwd` -> `SpawnCreateInput.session.source_execution_cwd` -> `PreparedSpawnPlan.session.source_execution_cwd`
- [ ] Trace (primary path): `resolve_session_reference()` -> `_ResolvedSessionTarget.source_execution_cwd` -> `LaunchRequest.session.source_execution_cwd` -> `ResolvedPrimaryLaunchPlan.source_execution_cwd`
- [ ] Trace (background worker): `BackgroundWorkerParams.source_execution_cwd` persisted/loaded -> `_execute_existing_spawn(source_execution_cwd=...)`
- [ ] All three resolver paths populate `source_execution_cwd` from records
