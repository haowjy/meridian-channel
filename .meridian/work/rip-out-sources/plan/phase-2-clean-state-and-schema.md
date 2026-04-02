# Phase 2: Clean State Paths + Remove Provenance/Bootstrap Schema Fields

## Scope
Remove install-related paths from `StatePaths`, clean the gitignore template, and remove dead `agent_source`/`skill_sources`/`bootstrap_*` fields from all runtime models, stores, and plumbing. Per CLAUDE.md: "No backwards compatibility needed — completely change the schema to get it right."

## State Paths

### `src/meridian/lib/state/paths.py`
- Remove from `StatePaths` model:
  - `agents_manifest_path`
  - `agents_local_manifest_path`
  - `agents_lock_path`
  - `agents_cache_dir`
- Remove corresponding assignments in `resolve_state_paths()`
- Remove from `_GITIGNORE_CONTENT`:
  - `"# Track shared install manifest and lock\n"`
  - `"!agents.toml\n"`
  - `"!agents.lock\n"`
- Remove from `_REQUIRED_GITIGNORE_LINES`:
  - `"!agents.toml"`
  - `"!agents.lock"`

### `src/meridian/lib/ops/config.py`
- In `ensure_state_bootstrap_sync()`, remove `state.agents_cache_dir` from `bootstrap_dirs` tuple

## Schema Field Removal

Remove `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` from all of these files:

### `src/meridian/lib/launch/types.py`
- Remove fields from `PrimarySessionMetadata` (lines 106-111):
  - `agent_source: str | None = None`
  - `skill_sources: dict[str, str]`
  - `bootstrap_required_items: tuple[str, ...]`
  - `bootstrap_missing_items: tuple[str, ...]`

### `src/meridian/lib/launch/resolve.py`
- Remove `skill_sources` field from `ResolvedSkills` dataclass (line 66)
- Remove `skill_sources` population in `resolve_skills_from_profile()` (lines 132-138)

### `src/meridian/lib/launch/plan.py`
- Remove parameters from `_build_session_metadata()`: `profile_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` (lines 105-107)
- Remove corresponding assignments in the function body (lines 114-119)

### `src/meridian/lib/launch/session_scope.py`
- Remove parameters from function signature: `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` (lines 34-39)
- Remove corresponding assignments in the function body (lines 55-60)

### `src/meridian/lib/launch/process.py`
- Remove `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` from all places they're passed through (lines 306-311, 337-342)

### `src/meridian/lib/launch/runner.py`
- Remove `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` passthrough (lines 722-727)

### `src/meridian/lib/ops/spawn/models.py`
- Remove fields from `SpawnActionOutput` (lines 66-71):
  - `agent_source: str | None = None`
  - `skill_sources: dict[str, str]`
  - `bootstrap_required_items: tuple[str, ...]`
  - `bootstrap_missing_items: tuple[str, ...]`
- Remove the wire serialization logic for these fields (lines 111-122)

### `src/meridian/lib/ops/spawn/plan.py`
- Remove fields (lines 51-54):
  - `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items`

### `src/meridian/lib/ops/spawn/api.py`
- Remove passthrough of these fields (lines 105-110)

### `src/meridian/lib/ops/spawn/execute.py`
- Remove passthrough in all places (lines 234-239, 291-302, 332-337, 350-355, 421-424, 463-468, 756-761)

### `src/meridian/lib/state/session_store.py`
- Remove fields from `SessionRecord` (lines 30-35)
- Remove fields from `SessionStartEvent` (lines 56-61)
- Remove from `_apply_start()` materialization (lines 122-127)
- Remove parameters from `start_session()` (lines 332-337)
- Remove from event construction in `start_session()` (lines 361-366)

### `src/meridian/lib/state/spawn_store.py`
- Remove fields from `SpawnRecord` (lines 72-77)
- Remove fields from `SpawnStartEvent` (lines 110-115)
- Remove parameters from `start_spawn()` (lines 187-192)
- Remove from event construction in `start_spawn()` (lines 222-227)
- Remove from resume defaults (lines 362-367)
- Remove from `_apply_start_event()` materialization (lines 418-436)

## Verification
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest-llm`
