# Phase 2b: Remove Provenance/Bootstrap Schema Fields

## Scope
Remove dead `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` fields from all runtime models, stores, and plumbing. These fields were populated by the install engine (deleted in Phase 1); with that engine gone, these fields are always empty/None.

Per AGENTS/CLAUDE guidance for this workstream: no backwards compatibility needed for schema cleanup.

Existing JSONL event files that still contain these keys remain readable because `SpawnStartEvent` and `SessionStartEvent` parse with `extra="ignore"`.

## IMPORTANT: Keep `_empty_template_vars` factory
In `ops/spawn/models.py`, `_empty_template_vars()` is shared by removed provenance fields and still-used `template_vars`. Remove provenance fields only; keep the factory for `template_vars` defaults.

## Files

### `src/meridian/lib/launch/types.py`
- In `PrimarySessionMetadata`, remove fields:
  - `agent_source`
  - `skill_sources`
  - `bootstrap_required_items`
  - `bootstrap_missing_items`

### `src/meridian/lib/launch/resolve.py`
- In `ResolvedSkills`, remove the `skill_sources` dataclass field.
- In `resolve_skills_for_run()`, remove the local `skill_sources = {...}` computation block.
- Update the `ResolvedSkills(...)` return construction to stop passing `skill_sources`.

### `src/meridian/lib/launch/plan.py`
- In `_build_session_metadata(...)`, remove parameters:
  - `profile_source`
  - `skill_sources`
  - `bootstrap_required_items`
  - `bootstrap_missing_items`
- In the metadata object construction inside `_build_session_metadata(...)`, remove assignment of those fields.

### `src/meridian/lib/launch/session_scope.py`
- In session scope builders/constructors, remove parameters:
  - `agent_source`
  - `skill_sources`
  - `bootstrap_required_items`
  - `bootstrap_missing_items`
- Remove corresponding assignments when creating session metadata/state payloads.

### `src/meridian/lib/launch/process.py`
- Remove all passthrough of the four removed fields when invoking session/runner/build helpers.

### `src/meridian/lib/launch/runner.py`
- Remove passthrough of the four removed fields in launch runner handoffs.

### `src/meridian/lib/ops/spawn/models.py`
- In `SpawnActionOutput`, remove fields:
  - `agent_source`
  - `skill_sources`
  - `bootstrap_required_items`
  - `bootstrap_missing_items`
- Remove wire serialization/output mapping for those fields.

### `src/meridian/lib/ops/spawn/plan.py`
- Remove the four removed fields from spawn planning models that mirror launch metadata.

### `src/meridian/lib/ops/spawn/api.py`
- Remove passthrough of the four removed fields in API-layer spawn model conversions.

### `src/meridian/lib/ops/spawn/prepare.py`
- Verify no residual passthrough remains for the four removed fields in spawn preparation output after Phase 1 deleted provenance/bootstrap resolution.

### `src/meridian/lib/ops/spawn/execute.py`
- Remove all passthrough and serialization of the four removed fields in execution and persistence paths.

### `src/meridian/lib/state/session_store.py`
- In `SessionRecord`, remove fields:
  - `agent_source`
  - `skill_sources`
  - `bootstrap_required_items`
  - `bootstrap_missing_items`
- In `SessionStartEvent`, remove the same four fields.
- In `_apply_start()` materialization logic, remove assignment of those fields.
- In `start_session(...)`, remove these parameters and stop including them in event construction.

### `src/meridian/lib/state/spawn_store.py`
- In `SpawnRecord`, remove fields:
  - `agent_source`
  - `skill_sources`
  - `bootstrap_required_items`
  - `bootstrap_missing_items`
- In `SpawnStartEvent`, remove the same four fields.
- In `start_spawn(...)`, remove these parameters and stop including them in event construction.
- In resume defaults and `_apply_start_event()` materialization, remove assignment/default handling for these fields.

### `tests/ops/test_spawn_prepare_fork.py`
- Update `ResolvedSkills(...)` test fixture construction to match the new signature (remove `skill_sources={}` argument).

## Verification
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest-llm`
