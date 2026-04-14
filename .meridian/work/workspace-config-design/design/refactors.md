# Refactor Agenda

## RF-1: Config File Resolution Extraction

**Current state**: `_resolve_project_toml()` in `settings.py` looks only at `.meridian/config.toml`. The path is hardcoded through `resolve_state_paths().config_path`.

**Target state**: `_resolve_project_toml()` checks `<repo_root>/meridian.toml` first, falls back to `.meridian/config.toml`. Emits advisory when both exist. New projects create at root.

**Why early**: Every other change depends on config loading correctly from the new location. Must land before workspace or gitignore changes.

**Scope**: Small. One function change in `settings.py`, update `StatePaths` to include root config path, update `_GITIGNORE_CONTENT` and `_REQUIRED_GITIGNORE_LINES` to remove `config.toml` exception.

**ID**: RF-1

---

## RF-2: Extract Harness Context Directory Resolution

**Current state**: `claude_preflight.py` reads parent Claude `additionalDirectories` inline and builds `--add-dir` flags directly. No shared function for directory collection/dedup.

**Target state**: Extract directory resolution into a shared function that collects context directories from all sources (workspace, parent settings, execution CWD, passthrough), deduplicates, and returns a clean list. Each harness projection consumes this list through its own flag format.

**Why early**: Without this, workspace directory injection would be hardcoded into `claude_preflight.py`. The extracted function becomes the single integration point for workspace context-roots.

**Scope**: Small. One function extraction from `claude_preflight.py`, one new shared function, callers updated.

**ID**: RF-2

---

## RF-3: Gitignore Helper for Repo Root

**Current state**: `.meridian/.gitignore` management exists in `state/paths.py`. No helper for managing entries in the repo root `.gitignore`.

**Target state**: Reusable `ensure_root_gitignored(repo_root: Path, entry: str)` that appends an entry to `<repo_root>/.gitignore` if not present. Used for `workspace.toml`.

**Why early**: Workspace init needs this. Config migration may also need to update root `.gitignore` (add `workspace.toml`, ensure `meridian.toml` is NOT gitignored).

**Scope**: Tiny. One utility function.

**ID**: RF-3

---

## RF-4: Models.toml Location Resolution

**Current state**: `models.toml` is loaded from `.meridian/models.toml` via catalog loading code.

**Target state**: Check `<repo_root>/models.toml` first, fall back to `.meridian/models.toml`. Same migration pattern as config.

**Why early**: Follows directly from RF-1 and should use the same pattern. Keeps the migration cohesive.

**Scope**: Small. Update the model catalog loader's file resolution. Same fallback-with-advisory pattern.

**ID**: RF-4
