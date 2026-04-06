# Implementation Status

| Phase | Description | Status |
|-------|------------|--------|
| 1 | Foundation — pattern_fallback_harness + _run_mars_models_resolve | ✅ done |
| 2 | Core rewrite — resolve_model + load_merged_aliases | ✅ done |
| 3 | Callers — resolve.py + registry.py + ops/catalog.py | ✅ done |
| 4 | Cleanup — remove dead code + models_toml + __all__ | ✅ done |
| 5 | Tests — update + add coverage | ✅ done |
| Fix | Mars broken = hard error (review finding) | ✅ done |

## Review Status
- Review round 1: 3 reviewers (opus, gpt-5.4, gpt-5.2) — converged on blocking finding
- Fix applied: mars broken raises RuntimeError instead of silent fallback
- All 214 tests pass, pyright 0 errors, ruff clean

## Deferred Items
- `models_config.py` still accepts `harness_patterns.*` config keys (separate PR)
- Missing deprecation warning for existing `[harness_patterns]` in models.toml (separate PR)
