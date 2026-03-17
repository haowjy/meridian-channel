# Model Catalog Improvements

## 1. Auto-resolve default aliases to latest model per family

**Current:** `default-aliases.toml` hardcodes `opus = "claude-opus-4-6"`. Goes stale when new models ship.

**Proposed:** Delete `default-aliases.toml`. Instead, auto-resolve builtin aliases (`opus`, `sonnet`, `haiku`, `codex`, `gpt`, `gemini`) to the latest discovered model in each family using `family` + `release_date` from the models.dev catalog. Users who want to pin a specific version set the alias in `.meridian/models.toml`.

**Key file:** `src/meridian/lib/catalog/models.py` — `_infer_family()` already groups models, `release_date` exists on `DiscoveredModel`.

## 2. CLI for managing models.toml

**Current:** Users must manually edit `.meridian/models.toml` to set aliases, roles, strengths. No CLI support.

**Proposed:**
```bash
meridian models describe codex --role "primary code implementer" --strengths "fast, structured edits"
meridian models alias mymodel gpt-5.4
meridian models unalias mymodel
```

Writes to `.meridian/models.toml`. Follows existing manifest-driven CLI pattern (`models_cmd.py`).

## 3. Model filtering (include/exclude)

**Current:** Hardcoded visibility heuristics in `_is_default_visible()` — hides `-latest` variants, old models, high-cost models. No user configuration.

**Proposed:** User-configurable wildcard include/exclude patterns in `.meridian/models.toml`:
```toml
[visibility]
exclude = ["gpt-5.1-*", "gemini-3-*"]
# or
include = ["claude-*", "gpt-5.3-*", "gpt-5.4"]
```

With sensible defaults (current heuristics as fallback).

## 4. Skill for model management

Add a skill in `meridian-base/` teaching agents how to manage models, aliases, descriptions, and filtering via CLI. Replace hardcoded model names in skills (like `review-orchestration`) with references to `meridian models list`.

## 5. Fix review-orchestration model references

`meridian-dev-workflow/skills/review-orchestration/SKILL.md` lists specific model names (gpt-5.4, opus, gpt-5.3-codex) in the Model Selection section. Replace with characteristic-based guidance and point to `meridian models list`. Same pattern as `__meridian-orchestrate` which already does this right.

## 6. Fix docs drift

`docs/configuration.md` shows `[[models]]` format but actual loader uses `[aliases]` tables. Sync docs with code.

## Research notes

- Models discovered from `https://models.dev/api.json` (providers: anthropic, openai, google)
- Only models with `tool_call` capability are kept
- Cache: `.meridian/cache/models.json`, 24h TTL
- Alias resolution: builtins loaded first, user `models.toml` overwrites by alias key
- `resolve_model()` chain: exact alias lookup → direct model ID → route_model validation
- Key files: `src/meridian/lib/catalog/models.py`, `src/meridian/lib/ops/catalog.py`, `src/meridian/cli/models_cmd.py`
