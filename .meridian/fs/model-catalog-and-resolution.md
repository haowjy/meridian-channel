# Model Catalog and Resolution

## What This Covers

How meridian resolves model names to concrete model IDs and harnesses. Covers the alias/resolution pipeline, the mars integration, the pattern fallback, and what was removed.

---

## Module Map

```
src/meridian/lib/catalog/
  model_aliases.py   — AliasEntry type, mars CLI integration, alias list loading
  model_policy.py    — Harness pattern fallback, visibility policy, superseded logic
  models.py          — resolve_model() entry point, models.dev discovery + cache
```

---

## Resolution Pipeline

`resolve_model(name_or_alias, repo_root)` in `models.py` is the single entry point.

### Step 1: Mars resolve (authoritative)

Calls `mars models resolve <name> --json` via `run_mars_models_resolve()` in `model_aliases.py`.

Mars is the **single authority** for alias→model_id mapping and harness routing. If mars returns a result with `harness_source != "unavailable"`, that harness is used directly. If mars resolves the alias but returns no harness, pattern fallback is applied to the resolved model ID.

If mars returns `harness_source == "unavailable"`, resolution raises a `ValueError` with a list of installable harness candidates — the user must install a harness first.

Mars binary is located via `_resolve_mars_binary()`: checks the same Python `scripts/` dir first, then `PATH`. If mars is absent, `RuntimeError` is raised — mars is always bundled with meridian, so absence is a hard error.

### Step 2: Pattern fallback (raw model IDs only)

If mars returns `None` (alias unknown), the input is treated as a raw model ID and routed via `pattern_fallback_harness()` in `model_policy.py`. This matches against `DEFAULT_HARNESS_PATTERNS`:

```python
DEFAULT_HARNESS_PATTERNS = {
    HarnessId.CLAUDE:    ("claude-*", "opus*", "sonnet*", "haiku*"),
    HarnessId.CODEX:     ("gpt-*", "o1*", "o3*", "o4*", "codex*"),
    HarnessId.OPENCODE:  ("opencode-*", "gemini*", "*/*"),
}
```

If no pattern matches, or multiple harnesses match, `ValueError` is raised.

### What was removed (models.toml era)

Previously meridian had its own internal model→harness routing:
- `models_toml.py` — TOML-based model config read from `.meridian/models.toml`
- `models_config.py` — model config merge logic
- `models_config_cmd.py` — `meridian models config` CLI surface
- `HarnessRegistry.route()` — registry-level routing method
- `harness_patterns` config surface — user-configurable patterns in meridian config

All of these are deleted. Mars is now the single source of truth for aliases and harness assignment.

---

## AliasEntry

`AliasEntry` in `model_aliases.py` is the resolved type returned by `resolve_model()`.

```python
class AliasEntry(BaseModel):
    alias: str              # empty string for raw model IDs
    model_id: ModelId
    resolved_harness: HarnessId | None   # excluded from serialization
    description: str | None              # excluded from serialization

    @property
    def harness(self) -> HarnessId:
        # returns resolved_harness if set, else pattern_fallback_harness(model_id)
```

The `harness` property always returns a concrete `HarnessId`. The `resolved_harness` field holds the value set at construction (from mars or pattern fallback); if None, the property falls through to pattern matching.

---

## Mars CLI Integration

Two mars commands are called:

| Function | Command | Used for |
|---|---|---|
| `run_mars_models_resolve(name)` | `mars models resolve <name> --json` | Primary resolution path |
| `_run_mars_models_list()` | `mars models list --json` | Alias listing for `meridian models list` |

`run_mars_models_resolve` is a **public API** (promoted from private in this session). It raises `RuntimeError` on mars binary failures and returns `None` when the alias is unknown.

`_run_mars_models_list` returns `None` on failure; callers fall back to reading `.mars/models-merged.json` directly.

---

## Alias Loading (for `meridian models list`)

`load_mars_aliases(repo_root)` in `model_aliases.py`:
1. Tries `mars models list --json` → `_mars_list_to_entries()`
2. Falls back to `.mars/models-merged.json` → `_mars_merged_to_entries()`
3. Returns empty list if both unavailable

The fallback file only contains pinned aliases (with explicit `model` key). Auto-resolve aliases (which resolve dynamically against the models cache) are skipped in the fallback path — they need mars to resolve.

---

## models.dev Discovery Cache

`load_discovered_models()` in `models.py` maintains a 24-hour TTL cache at `.meridian/cache/models.json`. Used by `meridian models list` to show model metadata (cost, context window, release date). Not involved in spawn-time resolution.

`ModelVisibilityConfig` / `DEFAULT_MODEL_VISIBILITY` in `model_policy.py` controls which discovered models are shown by default (excludes `-latest` aliases, very old models, expensive models, etc.). Previously this was configurable via `models.toml`; now it uses `DEFAULT_MODEL_VISIBILITY` with no user override surface (moving to mars eventually).

---

## Claude Adapter: Session File Resolution

`ClaudeAdapter.resolve_session_file()` in `harness/claude.py` was fixed in this session to search **all project dirs with matching slug prefix**, not just the exact repo root slug.

The issue: Claude creates project directories named after the full absolute path of the project root. If a session was started from a path that differs slightly (e.g., subdirectory, symlink resolution difference), the session file wouldn't be found.

Fix: `_candidate_claude_project_dirs(repo_root)` returns the primary slug dir + any dir under `~/.claude/projects/` whose name starts with the root slug. Both `resolve_session_file()` and `owns_untracked_session()` iterate all candidates.

---

## Key Design Decisions

**Mars as single authority**: Moving alias→harness routing out of meridian and into mars means meridian has no opinionated model list to maintain. New models become available by updating the mars package, not by editing meridian source. This also enables per-project model customization without touching meridian config.

**Pattern fallback for raw IDs**: Even with mars as authority, users need to pass raw model IDs (e.g., `claude-opus-4-6`) without defining an alias. Pattern fallback handles this case without requiring mars to enumerate every possible model ID. The patterns are intentionally simple and provider-prefix-based.

**No models.toml**: The config surface was removed entirely rather than deprecated. No real users means no migration burden. The `model_visibility` config surface may be reintroduced via mars later if needed.

**HarnessRegistry.route() deleted**: This was the old internal routing method that predated the mars integration. With `resolve_model()` now being the authoritative path, `route()` was redundant dead code.
