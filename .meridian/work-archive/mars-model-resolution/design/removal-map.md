# Removal Map

## What Gets Removed

### 1. `model_policy.py` — Config-driven routing plumbing (REMOVE)

**Remove:**
- `route_model_with_patterns()` — the configurable glob-based pattern matcher (replaced by `pattern_fallback_harness()`)
- `coerce_pattern_list()` — used only by harness_patterns config parsing
- `coerce_harness_patterns()` — used only by models.toml `[harness_patterns]`
- `merge_harness_patterns()` — used only by harness_patterns config merge
- `RoutingDecision` — replaced by AliasEntry.harness

**Keep:**
- `DEFAULT_HARNESS_PATTERNS` — retained as hardcoded fallback when mars is unavailable
- `match_pattern()` — **shared with model visibility** (`is_default_visible_model()` uses it for include/exclude patterns). NOT routing-only.
- `SpawnMode` — **used by `HarnessRegistry.route()` for direct mode**. Keep until direct mode is refactored.
- `ModelVisibilityConfig` and all visibility functions — display-only concern, unrelated to routing
- `compute_superseded_ids()`, `is_default_visible_model()` — display filtering

**Add:**
- `pattern_fallback_harness(model: str) -> HarnessId` — simplified routing using only `DEFAULT_HARNESS_PATTERNS`, no user config. Used when mars is unavailable and cached aliases don't have a harness.

### 2. `models.py` — Routing exports (REMOVE)

**Remove:**
- `load_harness_patterns()` — loads user harness_patterns from models.toml
- `route_model()` — wrapper around `route_model_with_patterns` with config loading
- `_resolve_alias_harness()` — backfills harness via route_model; no longer needed when mars provides harness

**Keep (NOT routing-only):**
- `_PROVIDER_TO_HARNESS` dict — **used by models.dev discovery pipeline** (`_parse_model_row()`, `_parse_models_payload()`). Maps provider names from models.dev JSON to harness IDs for `DiscoveredModel` entries. This is display/discovery, not routing.

**Simplify:**
- `resolve_model()` — three-step fallback: mars resolve → cached merged aliases → pattern fallback
- `load_merged_aliases()` — remove the `_resolve_alias_harness()` call; trust mars's harness field directly

**Update `__all__`:**
Remove dead exports: `RoutingDecision`, `route_model`, `route_model_with_patterns`, `load_harness_patterns`, `merge_harness_patterns`, `coerce_harness_patterns`.

### 3. `models_toml.py` — Harness patterns config (REMOVE)

**Remove from scaffold/render:**
- `[harness_patterns]` section in `scaffold_models_toml()` — no longer configurable in meridian
- `harness_patterns` handling in `render_models_toml()` — dead config
- Import of `DEFAULT_HARNESS_PATTERNS` (only used by scaffold)

**Keep:**
- `[model_visibility]` section — stays in meridian
- `[models]` section scaffolding — stays

### 4. `model_aliases.py` — Minor changes

**Change:**
- `AliasEntry.harness` property fallback: replace `route_model_with_patterns()` call with `pattern_fallback_harness()` from model_policy
- Update import from `route_model_with_patterns` → `pattern_fallback_harness`

### 5. `resolve.py` (launch) — Simplifications

**Simplify:**
- `resolve_harness()` — remove `route_model()` fallback path; use `resolve_model()` only
- `_derive_harness_from_model()` — collapse to single `resolve_model()` call
- `_resolve_final_model()` — same simplification

### 6. `harness/registry.py` — Remove routing dependency

**Simplify:**
- `HarnessRegistry.route()` harness mode: replace `route_model` import with `resolve_model`
- `HarnessRegistry.route()` direct mode: keep `SpawnMode` / use `HarnessId.DIRECT` directly
- Remove top-level `from meridian.lib.catalog.models import route_model`

### 7. `ops/catalog.py` — Update routing calls

**Simplify:**
- Replace any `route_model()` calls with `resolve_model()` 
- Remove `route_model` from imports

### 8. `.meridian/models.toml` — Schema change

**Remove sections:**
- `[harness_patterns]` — no longer read by meridian

**Migration:** On first run after upgrade, if `[harness_patterns]` exists in models.toml, log a deprecation warning pointing users to `mars.toml`.

## What Gets Added

### `model_aliases.py`

- `_run_mars_models_resolve(name, repo_root)` — calls `mars models resolve <name> --json`

### `model_policy.py`

- `pattern_fallback_harness(model: str) -> HarnessId` — simplified routing using only `DEFAULT_HARNESS_PATTERNS`, no user config merge. Raises ValueError if no pattern matches.

## Summary Table

| File | Lines removed (est.) | Lines added (est.) | Net |
|---|---|---|---|
| `model_policy.py` | ~50 (config routing plumbing) | ~15 (pattern_fallback_harness) | -35 |
| `models.py` | ~20 (route_model, load_harness_patterns, _resolve_alias_harness) | ~5 | -15 |
| `models_toml.py` | ~15 (harness_patterns scaffolding) | 0 | -15 |
| `model_aliases.py` | ~5 | ~25 (_run_mars_models_resolve) | +20 |
| `resolve.py` (launch) | ~15 | ~5 | -10 |
| `registry.py` (harness) | ~5 | ~3 | -2 |
| `ops/catalog.py` | ~3 | ~3 | 0 |
| **Total** | **~113** | **~56** | **~-57** |
