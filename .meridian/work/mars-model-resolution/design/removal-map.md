# Removal Map

## What Gets Removed

### 1. `model_policy.py` — Routing functions (REMOVE)

**Remove:**
- `route_model_with_patterns()` — the glob-based pattern matcher
- `match_pattern()` — used only by routing
- `coerce_pattern_list()` — used only by harness_patterns parsing
- `coerce_harness_patterns()` — used only by models.toml harness_patterns
- `merge_harness_patterns()` — used only by harness_patterns
- `RoutingDecision` — replaced by AliasEntry.harness
- `SpawnMode` — the "direct" mode is only used by `HarnessRegistry.route()` for direct harness, which can use a simpler check

**Keep:**
- `DEFAULT_HARNESS_PATTERNS` — retained as hardcoded fallback when mars is unavailable
- `ModelVisibilityConfig` and all visibility functions — display-only concern, unrelated to routing
- `compute_superseded_ids()`, `is_default_visible_model()` — display filtering

**Rename/Restructure:**
- The routing fallback function (`_pattern_route()`) replaces `route_model_with_patterns()` with a simpler signature that only uses `DEFAULT_HARNESS_PATTERNS` (no user config merge)

### 2. `models.py` — Routing exports (REMOVE)

**Remove:**
- `load_harness_patterns()` — loads user harness_patterns from models.toml
- `route_model()` — wrapper around `route_model_with_patterns` with config loading
- `_resolve_alias_harness()` — backfills harness via route_model; no longer needed when mars provides harness
- `_PROVIDER_TO_HARNESS` dict — redundant with mars's provider→harness tables

**Simplify:**
- `resolve_model()` — calls mars resolve first, pattern fallback second
- `load_merged_aliases()` — remove the `_resolve_alias_harness()` call; trust mars's harness field directly

### 3. `models_toml.py` — Harness patterns config (REMOVE)

**Remove from scaffold/render:**
- `[harness_patterns]` section in `scaffold_models_toml()` — no longer configurable in meridian
- `harness_patterns` handling in `render_models_toml()` — dead config

**Keep:**
- `[model_visibility]` section — stays in meridian
- `[models]` section scaffolding — stays (though aliases are configured in mars.toml, the models section may still have display annotations)

### 4. `model_aliases.py` — Minor cleanup

**No significant removals.** This module is already well-factored around mars integration. Small changes:
- `AliasEntry.harness` property fallback to `DEFAULT_HARNESS_PATTERNS` stays (needed when mars doesn't provide harness)
- Remove import of `route_model_with_patterns` if the property fallback moves to the simpler pattern match

### 5. `resolve.py` (launch) — Simplifications

**Simplify:**
- `resolve_harness()` — remove `route_model()` fallback path; use `resolve_model()` only
- `_derive_harness_from_model()` — collapse to single `resolve_model()` call
- `_resolve_final_model()` — same simplification

### 6. `harness/registry.py` — Remove routing dependency

**Simplify:**
- `HarnessRegistry.route()` — remove `route_model` import; use `resolve_model` for harness mode
- Remove top-level `from meridian.lib.catalog.models import route_model`

### 7. `.meridian/models.toml` — Schema change

**Remove sections:**
- `[harness_patterns]` — no longer read by meridian
- Models that are purely alias shortcuts move to `mars.toml [models]`

**Migration:** On first run after upgrade, if `[harness_patterns]` exists in models.toml, log a deprecation warning pointing users to `mars.toml`.

## What Gets Added

### `model_aliases.py`

- `_run_mars_models_resolve(name, repo_root)` — calls `mars models resolve <name> --json`

### `model_policy.py`

- `_pattern_fallback_harness(model: str) -> HarnessId` — simplified routing using only `DEFAULT_HARNESS_PATTERNS`, no user config merge. Used when mars is unavailable.

## Summary Table

| File | Lines removed (est.) | Lines added (est.) | Net |
|---|---|---|---|
| `model_policy.py` | ~70 (routing functions) | ~15 (pattern fallback) | -55 |
| `models.py` | ~30 (route_model, load_harness_patterns, _resolve_alias_harness) | ~5 | -25 |
| `models_toml.py` | ~15 (harness_patterns scaffolding) | 0 | -15 |
| `model_aliases.py` | ~5 | ~25 (_run_mars_models_resolve) | +20 |
| `resolve.py` (launch) | ~15 | ~5 | -10 |
| `registry.py` (harness) | ~5 | ~3 | -2 |
| **Total** | **~140** | **~53** | **~-87** |
