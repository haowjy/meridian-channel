# Phase Prep 3: Fork Provenance in SessionStartEvent

## Scope

Add `forked_from_chat_id: str | None = None` to `SessionStartEvent`, `SessionRecord`, and `start_session()`. Also add `parent_chat_id` lineage tracking. This is a data model change that must happen before fork is implemented — JSONL events can't be backfilled after the fact.

## Intent

When a fork creates a new session, the start event records which session it branched from. This is "knowledge in data, not code" per project principles. Without this field, fork lineage is permanently lost.

## Files to Modify

- **`src/meridian/lib/state/session_store.py`** — Add `forked_from_chat_id: str | None = None` to:
  - `SessionStartEvent` (after `started_at` field)
  - `SessionRecord` (after `active_work_id` field)
  - Update `_record_from_start_event()` to copy the field
  - Add `forked_from_chat_id: str | None = None` kwarg to `start_session()` and thread it into the `SessionStartEvent` constructor

- **`src/meridian/lib/launch/session_scope.py`** — Add `forked_from_chat_id: str | None = None` kwarg to `session_scope()` and pass through to `_start_session()`.

## Dependencies

- **Requires**: Prep 2 (logically follows, but technically independent — ordered here because provenance field is needed before fork implementation).
- **Produces**: `forked_from_chat_id` field on session events and records, `session_scope()` accepts it.

## Interface Contract

```python
# session_store.py
class SessionStartEvent(BaseModel):
    # ... existing fields ...
    forked_from_chat_id: str | None = None  # Set on fork, None otherwise

class SessionRecord(BaseModel):
    # ... existing fields ...
    forked_from_chat_id: str | None = None

def start_session(
    state_root: Path,
    harness: str,
    harness_session_id: str,
    model: str,
    # ... existing kwargs ...
    forked_from_chat_id: str | None = None,  # NEW
) -> str: ...

# session_scope.py
@contextmanager
def session_scope(
    *,
    state_root: Path,
    # ... existing kwargs ...
    forked_from_chat_id: str | None = None,  # NEW
) -> Iterator[ManagedSession]: ...
```

## Patterns to Follow

- See existing optional fields on `SessionStartEvent` like `agent_source: str | None = None` — same pattern.
- The `start_session` function already takes 12+ keyword arguments — one more optional `str | None` is minimal cost.
- Pydantic `extra="ignore"` on `SessionStartEvent` means old events without this field parse fine.

## Constraints

- Do NOT set `forked_from_chat_id` anywhere yet. All callers pass `None` (the default). Fork 5 will be the first caller to pass a non-None value.
- The field must be serialized in the JSONL event even when `None` — Pydantic default behavior handles this.
- Do NOT modify any CLI or spawn code.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] Existing sessions.jsonl files parse correctly (backward compatible)
- [ ] New session start events include `forked_from_chat_id: null` in JSON
