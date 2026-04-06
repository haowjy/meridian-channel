# Decision Log

## D1: CLI integration over Python import

**Decision:** Meridian calls mars via subprocess (`mars models resolve <name> --json`) rather than importing mars as a Python library.

**Why:** Mars is a Rust binary with no Python bindings. The subprocess pattern is already established (`_run_mars_models_list()` in `model_aliases.py`). Adding Python bindings would require PyO3 or cffi, adding build complexity for no benefit — the 10ms subprocess overhead is negligible in spawn context.

**Rejected:** Python bindings via PyO3. Adds build/packaging complexity, couples release cycles, and the CLI contract is already stable.

## D2: Keep DEFAULT_HARNESS_PATTERNS as hardcoded fallback

**Decision:** `DEFAULT_HARNESS_PATTERNS` stays in `model_policy.py` as a last-resort fallback when mars doesn't recognize a model (raw model IDs).

**Why:** Raw model IDs like `claude-opus-4-6` aren't in mars's alias registry. Pattern matching `claude-*` → claude harness is obvious and stable for these cases.

**Rejected:** Making all model IDs go through mars aliases. Would require mars to know every possible model ID, which is impractical.

## D3: Remove `[harness_patterns]` from models.toml

**Decision:** The `[harness_patterns]` section in `.meridian/models.toml` is removed. Users who customized harness→model mappings should move that config to `mars.toml [models]` as explicit aliases with harness fields.

**Why:** Two config locations for the same concern (model→harness mapping) is confusing. Mars's alias system is strictly more expressive.

**Constraint discovered:** Some users may have customized harness_patterns. A deprecation warning on first load is needed for migration (deferred to separate PR).

## D4: Trust mars's harness field directly

**Decision:** When mars resolves an alias, its `harness` field is used directly without re-validating against meridian's pattern table. The `_resolve_alias_harness()` function is removed.

**Why:** Re-routing after mars already resolved is the core of the redundancy problem. Mars's harness determination is more sophisticated (provider preference tables + installed CLI detection) than meridian's glob patterns.

## D5: `resolve_model()` becomes the single entry point

**Decision:** All callers go through `resolve_model()` which tries mars first, then pattern fallback. The separate `route_model()` function is removed from the public API.

**Why:** Having both `resolve_model()` and `route_model()` with different behaviors and fallback chains is the root cause of the inconsistency.

## D6: Two-step resolution, mars is required (revised post-user-feedback)

**Decision:** `resolve_model()` uses a two-step resolution: (1) `mars models resolve` CLI, (2) `DEFAULT_HARNESS_PATTERNS` for raw model IDs only. Mars being unavailable is a hard error, not a fallback trigger.

**Why:** Mars is bundled with meridian — it's always present. Removing the cached fallback simplifies the resolution chain and eliminates a code path that masks real errors.

**Implementation note (post-review):** `_run_mars_models_resolve()` raises `RuntimeError` for mars-binary-missing and subprocess-crash cases. Only exit code 1 (unknown alias) returns `None` for pattern fallback. Three reviewers converged on this being a blocking issue in the initial implementation — the fix distinguishes failure modes instead of returning `None` for all of them.

## D7: `harness_source=unavailable` is a hard error (post-review)

**Decision:** When mars resolves a model but reports `harness_source: "unavailable"`, meridian raises a ValueError with an actionable message including `harness_candidates`.

**Why:** Silently falling back to pattern matching when mars explicitly signals "no installed harness" would yield confusing downstream errors.

## D8: `_PROVIDER_TO_HARNESS` stays — it's discovery, not routing (post-review)

**Decision:** The `_PROVIDER_TO_HARNESS` dict in `models.py` is NOT removed. It's used by the models.dev discovery pipeline.

## D9: `match_pattern()` and `SpawnMode` stay — shared utilities (post-review)

**Decision:** `match_pattern()` stays (used by model visibility). `SpawnMode` stays (used by HarnessRegistry.route()).

## D10: Defer models_config.py harness_patterns cleanup (impl-time)

**Decision:** `models_config.py` still accepts `harness_patterns.*` config keys. Cleanup deferred to a separate PR.

**Why:** Reviewers (opus) correctly identified this as stale code that lets users set config that has no effect. However, the fix requires changes to `models_config.py` which is outside the scope of this plan's removal map and would need its own review. The behavioral impact is low — the config writes to models.toml but nothing reads the section anymore. Fixing it in a separate focused PR avoids scope creep.
