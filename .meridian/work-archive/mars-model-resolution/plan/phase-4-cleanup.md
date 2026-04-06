# Phase 4: Cleanup — Remove Dead Code + Update Exports

## Scope

Remove functions and config plumbing that are no longer called after Phase 2-3. Update `__all__` exports. Clean up `models_toml.py` scaffold/render.

## Files to Modify

- `src/meridian/lib/catalog/model_policy.py` — remove dead routing functions
- `src/meridian/lib/catalog/models.py` — remove dead functions + update `__all__`
- `src/meridian/lib/catalog/models_toml.py` — remove harness_patterns from scaffold/render

## What to Remove

### `model_policy.py` — Remove config-driven routing plumbing

Remove these functions (they have zero callers after Phase 2-3):
- `RoutingDecision` class (lines 16-22) — replaced by `AliasEntry.harness`
- `route_model_with_patterns()` (lines 135-161) — replaced by `pattern_fallback_harness()`
- `coerce_pattern_list()` (lines 58-69) — used only by `coerce_harness_patterns()`
- `coerce_harness_patterns()` (lines 72-93) — used only by models.toml harness_patterns config
- `merge_harness_patterns()` (lines 120-126) — used only by `load_harness_patterns()`

**Keep** (shared utilities — Decision D9):
- `match_pattern()` — used by `is_default_visible_model()` and `pattern_fallback_harness()`
- `SpawnMode` — used by `HarnessRegistry.route()` type signatures
- `DEFAULT_HARNESS_PATTERNS` — used by `pattern_fallback_harness()`
- All visibility functions and config (`ModelVisibilityConfig`, `coerce_model_visibility`, etc.)

### `models.py` — Remove dead functions + update __all__

Remove:
- `load_harness_patterns()` (lines 52-61) — no callers
- `route_model()` (lines 64-76) — no callers after Phase 3
- `_resolve_alias_harness()` — already removed in Phase 2

Remove from imports (no longer used in this file):
- `RoutingDecision` from model_policy import
- `coerce_harness_patterns` from model_policy import
- `merge_harness_patterns` from model_policy import
- `route_model_with_patterns` from model_policy import

Add to imports:
- `pattern_fallback_harness` from model_policy (if not already added in Phase 2)

Update `__all__` — remove these dead exports:
- `"RoutingDecision"`
- `"route_model"`
- `"route_model_with_patterns"`
- `"load_harness_patterns"`
- `"merge_harness_patterns"`
- `"coerce_harness_patterns"`

Keep in `__all__`:
- `"SpawnMode"` — still exported (Decision D9)
- Everything else that's still alive

### `models_toml.py` — Remove harness_patterns scaffolding

In `scaffold_models_toml()`:
- Remove the commented `[harness_patterns]` section lines (lines 56-59)
- Remove the `DEFAULT_HARNESS_PATTERNS` import (line 10) — only used by scaffold

In `render_models_toml()`:
- Remove the `harness_patterns` rendering block (lines 107-114)

Keep:
- `[model_visibility]` section in both scaffold and render
- `[models]` section in both
- `DEFAULT_MODEL_VISIBILITY` import (still used by scaffold)

## Dependencies

- Requires: Phase 2 (dead code is dead only after resolve_model rewrite)
- Independent of: Phase 3

## Constraints

- Verify each function has zero callers before removing — use grep
- Do NOT remove `_PROVIDER_TO_HARNESS` in models.py (Decision D8 — it's discovery, not routing)
- Do NOT remove `SpawnMode` (Decision D9)
- Do NOT remove `match_pattern()` (Decision D9)

## Verification Criteria

- [ ] `uv run pyright` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] `grep -r "route_model_with_patterns\|coerce_harness_patterns\|merge_harness_patterns\|load_harness_patterns\|RoutingDecision" src/meridian/` returns nothing (except this plan)
- [ ] `from meridian.lib.catalog.models import resolve_model, SpawnMode` works
- [ ] `from meridian.lib.catalog.model_policy import pattern_fallback_harness, match_pattern, SpawnMode` works
