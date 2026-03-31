# Phase 2b: Expand SessionContinuation as the Continuation Carrier (R3)

## Scope

Consolidate continuation metadata so it flows through both spawn and primary launch paths via `SessionContinuation`. Currently, continuation fields are scattered across 6 DTOs. Phase 3 needs to add `source_execution_cwd` -- doing that in one place instead of six is the goal.

After this phase, `SessionContinuation` carries all continuation-related fields. Other DTOs embed or reference it rather than duplicating individual fields.

This phase depends on:
- **Phase 1d**: Clean resolver with shared `_build_tracked_reference()` builder

## Files to Modify

### `src/meridian/lib/ops/spawn/plan.py`

Expand `SessionContinuation` to carry all continuation-related fields:

```python
class SessionContinuation(BaseModel):
    """Continuation options for harness session reuse.

    Single carrier of continuation state through both spawn command path
    and primary launch path. Phase 3 adds source_execution_cwd here.
    """

    model_config = ConfigDict(frozen=True)

    harness_session_id: str | None = None
    continue_fork: bool = False
    forked_from_chat_id: str | None = None  # NEW: moved from individual DTO fields
```

### `src/meridian/lib/ops/spawn/models.py`

Add a `session` field to `SpawnCreateInput` that carries the consolidated continuation:

```python
class SpawnCreateInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    # ... existing fields ...
    # Continuation metadata -- prefer session field for new code.
    session: SessionContinuation = Field(default_factory=SessionContinuation)
    # Legacy individual fields kept for backward compatibility.
    # New code should read from session.* instead.
    continue_harness_session_id: str | None = None
    continue_harness: str | None = None
    continue_source_tracked: bool = False
    continue_source_ref: str | None = None
    continue_fork: bool = False
    forked_from_chat_id: str | None = None
```

Import `SessionContinuation` from `plan.py`:
```python
from meridian.lib.ops.spawn.plan import SessionContinuation
```

### `src/meridian/lib/launch/types.py`

Add a `session` field to `LaunchRequest`:

```python
from meridian.lib.ops.spawn.plan import SessionContinuation

class LaunchRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    # ... existing fields ...
    session: SessionContinuation = Field(default_factory=SessionContinuation)
    # Legacy individual fields kept for backward compatibility.
    continue_harness_session_id: str | None = None
    continue_chat_id: str | None = None
    continue_fork: bool = False
    forked_from_chat_id: str | None = None
```

**Import note**: `launch/types.py` importing from `ops/spawn/plan.py` creates a new dependency direction (launch/ -> ops/spawn/). Current import analysis shows `plan.py` does NOT import from `launch/`, so no circular dependency exists. To verify:
1. Check `ops/spawn/plan.py` imports -- should only import from `harness.adapter` and `safety.permissions`
2. Run `uv run pyright` -- it will catch circular imports
3. If circular imports surface at any point, the fallback is: move `SessionContinuation` to `lib/core/continuation.py` and have both modules import from there

### `src/meridian/lib/ops/reference.py`

Add `source_execution_cwd` placeholder to `ResolvedSessionReference`:

No changes needed in Phase 2b -- `source_execution_cwd` is added in Phase 3.

**However**, update `_build_tracked_reference()` (from Phase 1d) to accept and return continuation-related fields that Phase 3 will need. This means accepting an optional `execution_cwd` parameter:

Actually, keep Phase 2b focused on DTO consolidation. The `_build_tracked_reference` gets its `source_execution_cwd` parameter in Phase 3.

### `src/meridian/cli/spawn.py`

Update `_spawn_create()` fork path (~line 270) to populate the `session` field on `SpawnCreateInput`:

```python
result = spawn_create_sync(
    SpawnCreateInput(
        # ... existing fields ...
        session=SessionContinuation(
            harness_session_id=resolved_reference.harness_session_id,
            continue_fork=True,
            forked_from_chat_id=resolved_reference.source_chat_id,
        ),
        # Keep legacy fields populated for any code still reading them.
        continue_harness_session_id=resolved_reference.harness_session_id,
        continue_harness=resolved_reference.harness,
        continue_source_tracked=resolved_reference.tracked,
        continue_source_ref=resolved_fork_from,
        continue_fork=True,
        forked_from_chat_id=resolved_reference.source_chat_id,
    ),
    sink=current_output_sink(),
)
```

### `src/meridian/cli/main.py`

Update the fork path in `_run_primary_launch()` to populate the `session` field on `LaunchRequest`:

```python
launch_result = launch_primary(
    repo_root=repo_root,
    request=LaunchRequest(
        # ... existing fields ...
        session=SessionContinuation(
            harness_session_id=continue_harness_session_id,
            continue_fork=continue_fork,
            forked_from_chat_id=forked_from_chat_id,
        ),
        # Keep legacy fields populated.
        continue_harness_session_id=continue_harness_session_id,
        continue_chat_id=continue_chat_id,
        continue_fork=continue_fork,
        forked_from_chat_id=forked_from_chat_id,
    ),
    harness_registry=harness_registry,
)
```

### `src/meridian/lib/ops/spawn/prepare.py`

Update `build_create_payload()` to read continuation from the new `session` field:

```python
# Prefer session field, fall back to legacy individual fields.
resolved_continue_harness_session_id = (
    payload.session.harness_session_id
    or (payload.continue_harness_session_id or "").strip()
    or None
)
resolved_continue_fork = payload.session.continue_fork or payload.continue_fork
resolved_forked_from = (
    payload.session.forked_from_chat_id
    or payload.forked_from_chat_id
)
```

And construct SessionContinuation with the resolved values:

```python
session=SessionContinuation(
    harness_session_id=resolved_continue_harness_session_id,
    continue_fork=resolved_continue_fork,
    forked_from_chat_id=resolved_forked_from,
),
```

## Dependencies

- **Requires**: Phase 1d (clean resolver builder with `_build_tracked_reference()`)
- **Produces**: Consolidated `SessionContinuation` DTO that flows through both paths. Phase 3 adds `source_execution_cwd` to this ONE DTO plus `ResolvedSessionReference`, instead of threading it through 6+ scattered DTOs.

## Constraints

- **Legacy fields MUST be preserved** on SpawnCreateInput and LaunchRequest for backward compatibility. Existing code that reads `payload.continue_harness_session_id` must still work. Phase 3 can migrate readers to `payload.session.*` as it threads the new field.
- Keep `SessionContinuation` in `ops/spawn/plan.py` unless circular imports force a move. If moved, update all imports.
- `_ResolvedSessionTarget` in main.py does NOT need changes in this phase -- it's a local DTO that will be updated when Phase 3 threads `source_execution_cwd`.
- Do NOT add `source_execution_cwd` to any DTO in this phase -- that's Phase 3.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] `SessionContinuation` has `forked_from_chat_id` field
- [ ] `SpawnCreateInput` has `session: SessionContinuation` field
- [ ] `LaunchRequest` has `session: SessionContinuation` field
- [ ] CLI spawn.py populates both `session` and legacy fields
- [ ] CLI main.py populates both `session` and legacy fields
- [ ] prepare.py reads from `session` field with fallback to legacy fields
- [ ] No circular import issues between launch/types.py and ops/spawn/plan.py
