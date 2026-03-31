# Phase 1a: Add `execution_cwd` to Data Models

## Scope

Add the `execution_cwd` field to both the spawn and session event stores. This establishes the data model foundation that all subsequent phases depend on. After this phase, the stores can carry and project `execution_cwd`, but nothing writes it yet.

## Files to Modify

### `src/meridian/lib/state/spawn_store.py`

1. **`SpawnRecord`** (line 68): Add field `execution_cwd: str | None = None`
2. **`SpawnStartEvent`** (line 104): Add field `execution_cwd: str | None = None`
3. **`SpawnUpdateEvent`** (line 132): Add field `execution_cwd: str | None = None`
4. **`_empty_record()`** (line 350): Add `execution_cwd=None` to the returned `SpawnRecord`
5. **`_record_from_events()`** -- `SpawnStartEvent` branch (line 400): Add projection:
   ```python
   "execution_cwd": (
       event.execution_cwd if event.execution_cwd is not None else current.execution_cwd
   ),
   ```
6. **`_record_from_events()`** -- `SpawnUpdateEvent` branch (line 457): Add projection:
   ```python
   "execution_cwd": (
       event.execution_cwd if event.execution_cwd is not None else current.execution_cwd
   ),
   ```

### `src/meridian/lib/state/session_store.py`

1. **`SessionRecord`** (line 19): Add field `execution_cwd: str | None = None`
2. **`SessionStartEvent`** (line 43): Add field `execution_cwd: str | None = None`
3. **`_record_from_start_event()`** (line 110): Add `execution_cwd=event.execution_cwd` to the returned `SessionRecord`

## Dependencies

- **Requires**: Nothing -- this is the foundation phase.
- **Produces**: Data model fields consumed by Phase 2a (recording) and Phase 3 (reference resolver reads `execution_cwd` from records).

## Patterns to Follow

Follow the existing pattern for optional fields in both stores. Look at how `harness_session_id` or `work_id` are added to the same models -- `execution_cwd` follows the identical pattern. The field is `str | None` with default `None`, and projection uses the "latest non-None wins" merge.

## Constraints

- Do NOT modify function signatures (`start_spawn`, `update_spawn`, `start_session`) in this phase -- that's Phase 2a.
- The field must survive round-trip through JSONL serialization (Pydantic handles this automatically with `str | None`).
- Both `SpawnStartEvent` and `SpawnUpdateEvent` need the field because Phase 2a writes it from both layers (initial pre-compute on start, authoritative correction on update).

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] `SpawnRecord`, `SpawnStartEvent`, `SpawnUpdateEvent` all have `execution_cwd: str | None = None`
- [ ] `SessionRecord`, `SessionStartEvent` both have `execution_cwd: str | None = None`
- [ ] `_record_from_events` projects `execution_cwd` in both event branches
- [ ] `_empty_record` includes `execution_cwd=None`
- [ ] `_record_from_start_event` passes `execution_cwd=event.execution_cwd`
