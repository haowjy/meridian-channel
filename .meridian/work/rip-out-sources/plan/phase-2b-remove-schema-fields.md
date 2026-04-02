# Phase 2b: Remove Provenance/Bootstrap Schema Fields

## Scope
Remove dead `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` fields from all runtime models, stores, and plumbing. These were populated by the install engine (deleted in Phase 1); with it gone, they're always empty/None.

Per CLAUDE.md: "No backwards compatibility needed — completely change the schema to get it right."

Note: existing JSONL event files with these fields will parse fine — `SpawnStartEvent` and `SessionStartEvent` use `extra="ignore"` in their Pydantic config, so unknown fields are silently dropped.

## IMPORTANT: Do NOT delete `_empty_template_vars` factory
In `ops/spawn/models.py`, the `_empty_template_vars()` factory (line 12) is shared between `skill_sources` AND `template_vars`. After removing `skill_sources`, it still serves `template_vars`. Keep it.

## Files

### `src/meridian/lib/launch/types.py`
- Remove fields from `PrimarySessionMetadata` (lines 106-111):
  - `agent_source: str | None = None`
  - `skill_sources: dict[str, str]`
  - `bootstrap_required_items: tuple[str, ...]`
  - `bootstrap_missing_items: tuple[str, ...]`

### `src/meridian/lib/launch/resolve.py`
- Remove `skill_sources` field from `ResolvedSkills` dataclass (line 66) — dead code, computed but never consumed downstream
- Remove `skill_sources = { ... }` computation block (lines 132-134)
- Remove `skill_sources=skill_sources` from return statement (line 138)

### `src/meridian/lib/launch/plan.py`
- Remove parameters from `_build_session_metadata()`: `profile_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` (lines 105-107)
- Remove corresponding assignments in the function body (lines 114-119)

### `src/meridian/lib/launch/session_scope.py`
- Remove parameters: `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` (lines 34-39)
- Remove corresponding assignments (lines 55-60)

### `src/meridian/lib/launch/process.py`
- Remove passthrough of these 4 fields (lines 306-311, 337-342)

### `src/meridian/lib/launch/runner.py`
- Remove passthrough (lines 722-727)

### `src/meridian/lib/ops/spawn/models.py`
- Remove fields from `SpawnActionOutput` (lines 66-71)
- Remove wire serialization logic for these fields (lines 111-122)

### `src/meridian/lib/ops/spawn/plan.py`
- Remove fields (lines 51-54)

### `src/meridian/lib/ops/spawn/api.py`
- Remove passthrough (lines 105-110)

### `src/meridian/lib/ops/spawn/prepare.py`
- Remove passthrough of these fields where they were fed from the now-deleted provenance/bootstrap calls (lines 380-383 already cleared in Phase 1, but verify no remnants)

### `src/meridian/lib/ops/spawn/execute.py`
- Remove passthrough in all places (~28 references across lines 234-239, 291-302, 332-337, 350-355, 421-424, 463-468, 756-761)

### `src/meridian/lib/state/session_store.py`
- Remove fields from `SessionRecord` (lines 30-35)
- Remove fields from `SessionStartEvent` (lines 56-61)
- Remove from `_apply_start()` materialization (lines 122-127)
- Remove parameters from `start_session()` (lines 332-337)
- Remove from event construction (lines 361-366)

### `src/meridian/lib/state/spawn_store.py`
- Remove fields from `SpawnRecord` (lines 72-77)
- Remove fields from `SpawnStartEvent` (lines 110-115)
- Remove parameters from `start_spawn()` (lines 187-192)
- Remove from event construction (lines 222-227)
- Remove from resume defaults (lines 362-367)
- Remove from `_apply_start_event()` materialization (lines 418-436)

### `tests/ops/test_spawn_prepare_fork.py`
- Remove `ResolvedSkills(skill_sources={})` — update to match new `ResolvedSkills` signature (field was removed from dataclass above)

## Verification
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest-llm`
