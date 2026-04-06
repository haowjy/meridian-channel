# Decision Log

## D1: CLI integration over Python import

**Decision:** Meridian calls mars via subprocess (`mars models resolve <name> --json`) rather than importing mars as a Python library.

**Why:** Mars is a Rust binary with no Python bindings. The subprocess pattern is already established (`_run_mars_models_list()` in `model_aliases.py`). Adding Python bindings would require PyO3 or cffi, adding build complexity for no benefit — the 10ms subprocess overhead is negligible in spawn context.

**Rejected:** Python bindings via PyO3. Adds build/packaging complexity, couples release cycles, and the CLI contract is already stable.

## D2: Keep DEFAULT_HARNESS_PATTERNS as hardcoded fallback

**Decision:** `DEFAULT_HARNESS_PATTERNS` stays in `model_policy.py` as a last-resort fallback when mars is unavailable or doesn't recognize a model.

**Why:** Mars may not be installed (fresh repo, CI environments). A user typing `meridian spawn -m claude-opus-4-6` should still work without mars — the pattern `claude-*` → claude harness is obvious and stable. Removing the fallback would make mars a hard dependency.

**Rejected:** Making mars a hard dependency. Meridian should degrade gracefully. Also rejected: keeping user-configurable harness_patterns in models.toml — that config belongs in mars.toml now.

## D3: Remove `[harness_patterns]` from models.toml

**Decision:** The `[harness_patterns]` section in `.meridian/models.toml` is removed. Users who customized harness→model mappings should move that config to `mars.toml [models]` as explicit aliases with harness fields.

**Why:** Two config locations for the same concern (model→harness mapping) is confusing. Mars's alias system is strictly more expressive — it supports pinned aliases, auto-resolve with patterns, provider inference, and installed CLI detection. Meridian's glob patterns are a subset of that functionality.

**Constraint discovered:** Some users may have customized harness_patterns. A deprecation warning on first load is needed for migration.

## D4: Trust mars's harness field directly

**Decision:** When mars resolves an alias, its `harness` field is used directly without re-validating against meridian's pattern table. The `_resolve_alias_harness()` function is removed.

**Why:** Re-routing after mars already resolved is the core of the redundancy problem. Mars's harness determination is more sophisticated (provider preference tables + installed CLI detection) than meridian's glob patterns. Double-routing can only disagree, never improve.

**Risk:** If mars returns a harness that meridian doesn't have a registered adapter for, the spawn fails. This is the correct behavior — it means the harness binary exists (mars detected it) but meridian doesn't have an adapter. That's an integration gap to fix in meridian, not a reason to override mars.

## D5: `resolve_model()` becomes the single entry point

**Decision:** All callers go through `resolve_model()` which tries mars first, then pattern fallback. The separate `route_model()` function is removed from the public API.

**Why:** Having both `resolve_model()` and `route_model()` with different behaviors and fallback chains is the root cause of the inconsistency. A single function with a clear fallback chain (mars → patterns) is simpler to reason about and test.

## D6: Three-step fallback chain (post-review)

**Decision:** `resolve_model()` uses a three-step fallback: (1) `mars models resolve` CLI, (2) `.mars/models-merged.json` cached aliases, (3) `DEFAULT_HARNESS_PATTERNS` pattern matching.

**Why:** Reviewers (p950, p952) identified that the initial design skipped step 2, which would regress `-m opus` in environments where mars is not installed but `.mars/models-merged.json` exists (e.g., after `mars sync` was run but mars binary was later removed). The existing `_read_mars_merged_file()` function already handles this path.

**Rejected:** Two-step fallback (mars → patterns). Would break pinned alias resolution when mars binary is absent.

## D7: `harness_source=unavailable` is a hard error (post-review)

**Decision:** When mars resolves a model but reports `harness_source: "unavailable"`, meridian raises a ValueError with an actionable message including `harness_candidates`.

**Why:** Reviewer p952 identified that silently falling back to pattern matching when mars explicitly signals "no installed harness" would yield confusing downstream errors — the pattern match would pick a harness family that also isn't installed.

**Rejected:** Silent fallback with warning. The user needs to install a harness; falling through to patterns just delays the same error.

## D8: `_PROVIDER_TO_HARNESS` stays — it's discovery, not routing (post-review)

**Decision:** The `_PROVIDER_TO_HARNESS` dict in `models.py` is NOT removed. It's used by the models.dev discovery pipeline (`_parse_model_row()`, `_parse_models_payload()`) to convert raw API data into `DiscoveredModel` entries for `meridian models list`.

**Why:** Reviewer p951 identified that the initial removal map conflated two distinct uses of provider→harness mapping: routing (being delegated to mars) and discovery/display (staying in meridian). Removing it would break `fetch_models_dev()` and `refresh_models_cache()`.

## D9: `match_pattern()` and `SpawnMode` stay — shared utilities (post-review)

**Decision:** `match_pattern()` stays because it's used by model visibility (`is_default_visible_model()`). `SpawnMode` stays because it's used by `HarnessRegistry.route()` for direct mode.

**Why:** Reviewers p951 and p952 both identified these as shared utilities incorrectly marked for removal. Only the config-driven routing plumbing is removed.
