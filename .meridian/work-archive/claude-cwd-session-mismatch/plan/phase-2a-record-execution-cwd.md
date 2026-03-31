# Phase 2a: Record `execution_cwd` at the Right Layers

## Scope

Wire the `execution_cwd` parameter through the store APIs, session lifecycle, and execution layers so every spawn and session records where its harness process actually runs. After this phase, new spawn/session records carry `execution_cwd` on disk.

This phase depends on:
- **Phase 1a**: data model fields exist on events and records
- **Phase 1b**: `resolve_child_execution_cwd()` helper exists in `launch/cwd.py`
- **Phase 1c**: `BackgroundWorkerParams` model exists (add `execution_cwd` field to it)

## Files to Modify

### `src/meridian/lib/state/spawn_store.py`

1. **`start_spawn()`** (line 181): Add parameter `execution_cwd: str | None = None`. Pass it to `SpawnStartEvent(execution_cwd=execution_cwd, ...)`.
2. **`update_spawn()`** (line 248): Add parameter `execution_cwd: str | None = None`. Pass it to `SpawnUpdateEvent(execution_cwd=execution_cwd, ...)`.

### `src/meridian/lib/state/session_store.py`

1. **`start_session()`** (line 320): Add parameter `execution_cwd: str | None = None`. Pass it to `SessionStartEvent(execution_cwd=execution_cwd, ...)`.

### `src/meridian/lib/launch/session_scope.py`

1. **`session_scope()`** (line 24): Add parameter `execution_cwd: str | None = None`. Pass it through to the `_start_session()` call (line 45) as `execution_cwd=execution_cwd`.

### `src/meridian/lib/ops/spawn/execute.py`

This file has three spawn execution paths. All three need `execution_cwd`.

1. **`_session_execution_context()`** (line 296): Add parameter `execution_cwd: str | None = None`. Pass through to `session_scope()` call (line 314).

2. **`_init_spawn()`** (line 190): Add parameter `execution_cwd: str | None = None`. Pass through to `spawn_store.start_spawn()` call (line 212).

3. **`execute_spawn_blocking()`** (line 661): After `_init_spawn()`, compute execution_cwd using the shared helper from Phase 1b:
   ```python
   from meridian.lib.launch.cwd import resolve_child_execution_cwd

   # Pre-compute execution CWD. Mirrors runner.py's CWD-flip decision.
   # See launch/cwd.py for the shared predicate. Both sites must stay in sync.
   execution_cwd_path = resolve_child_execution_cwd(
       repo_root=runtime.repo_root,
       spawn_id=str(context.spawn.spawn_id),
       harness_id=prepared.harness_id,
   )
   execution_cwd_str = str(execution_cwd_path)
   ```
   Pass `execution_cwd=execution_cwd_str` to `_session_execution_context()` and to `_init_spawn()`.

   **Note on ordering**: `_init_spawn()` is called BEFORE `execution_cwd_path` is computed (it creates the spawn_id). Initial `_init_spawn()` gets `execution_cwd=str(runtime.repo_root)`. After spawn_id is known and execution_cwd computed, call `spawn_store.update_spawn(context.state_root, context.spawn.spawn_id, execution_cwd=execution_cwd_str)` if the values differ.

4. **`execute_spawn_background()`** (line 523): Same pattern -- pass `execution_cwd=str(runtime.repo_root)` to `_init_spawn()`. The runner.py update will correct it. Also add `execution_cwd` to `BackgroundWorkerParams` (the Phase 1c model) so the background worker can pass it through.

5. **`_execute_existing_spawn()`** (line 342): Add parameter `execution_cwd: str | None = None`. Pass to `_session_execution_context()` call. For background workers, this comes from `BackgroundWorkerParams.execution_cwd` (loaded from disk by Phase 1c).

6. **`BackgroundWorkerParams`** (from Phase 1c): Add `execution_cwd: str | None = None` field. The `execute_spawn_background()` caller computes it via `resolve_child_execution_cwd()` and includes it in the persisted params.

### `src/meridian/lib/launch/runner.py`

1. **`execute_with_finalization()`** -- After the CWD flip block (after `resolve_child_execution_cwd` usage from Phase 1b), add the authoritative update:
   ```python
   # Record the actual execution CWD on the spawn record.
   # This is the authoritative value -- mirrors the pre-compute in execute.py.
   # See design-spec.md Part 2 for the dual-site contract.
   spawn_store.update_spawn(
       state_root,
       run.spawn_id,
       execution_cwd=str(child_cwd),
   )
   ```
   This goes right after the CWD flip logic, before the retry loop.

### `src/meridian/lib/launch/process.py`

1. **`run_harness_process()`** -- `session_scope()` call (line 293): Add `execution_cwd=str(repo_root)`.
2. **`run_harness_process()`** -- `spawn_store.start_spawn()` call (line 326): Add `execution_cwd=str(repo_root)`.

## Dependencies

- **Requires**: Phase 1a (data model fields), Phase 1b (shared CWD helper), Phase 1c (BackgroundWorkerParams model)
- **Produces**: `execution_cwd` values on all new spawn and session records. Phase 3 reads these from the reference resolver.

## Interface Contract

```python
# spawn_store.py
def start_spawn(state_root, *, ..., execution_cwd: str | None = None) -> SpawnId
def update_spawn(state_root, spawn_id, *, ..., execution_cwd: str | None = None) -> None

# session_store.py
def start_session(state_root, ..., execution_cwd: str | None = None) -> str

# session_scope.py
def session_scope(*, ..., execution_cwd: str | None = None) -> Iterator[ManagedSession]

# execute.py
class BackgroundWorkerParams(BaseModel):
    ...
    execution_cwd: str | None = None  # NEW FIELD added to Phase 1c's model
```

## Constraints

- The pre-compute condition in `execute.py` MUST use `resolve_child_execution_cwd()` from Phase 1b (NOT inline the condition). Add a code comment pointing to `runner.py` as the authoritative site.
- `HarnessId.CLAUDE.value` is the string `"claude"` -- `resolve_child_execution_cwd()` already handles string comparison.
- All new parameters default to `None` for backward compatibility.
- The `execution_cwd` stored is always a string (not a Path) for JSON serialization.
- Primary launches (process.py) always use `repo_root` as execution_cwd since they don't do CWD flipping.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] Trace: `execute_spawn_blocking` -> `_init_spawn(execution_cwd=...)` -> `start_spawn(execution_cwd=...)` -> `SpawnStartEvent.execution_cwd` set
- [ ] Trace: `execute_spawn_blocking` -> `_session_execution_context(execution_cwd=...)` -> `session_scope(execution_cwd=...)` -> `start_session(execution_cwd=...)` -> `SessionStartEvent.execution_cwd` set
- [ ] Trace: `runner.py` CWD flip -> `update_spawn(execution_cwd=str(child_cwd))` -> `SpawnUpdateEvent.execution_cwd` set
- [ ] Trace: `process.py` -> `session_scope(execution_cwd=str(repo_root))` and `start_spawn(execution_cwd=str(repo_root))`
- [ ] `BackgroundWorkerParams` has `execution_cwd` field; background path persists and loads it
