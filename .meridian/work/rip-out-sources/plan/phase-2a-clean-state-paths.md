# Phase 2a: Clean State Paths and Gitignore

## Scope
Remove install-related paths from `StatePaths` and clean the gitignore template. Mechanical cleanup — direct consequence of Phase 1 deleting the install module.

## Files

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

### `.meridian/.gitignore` (checked-in file)
- Manually remove existing `!agents.toml` and `!agents.lock` lines from the checked-in file.
- Rationale: `ensure_gitignore()` appends/strips based on template content; it does not reliably clean stale tracked lines already present on disk.

## Verification
- `uv run ruff check .`
- `uv run pyright`
