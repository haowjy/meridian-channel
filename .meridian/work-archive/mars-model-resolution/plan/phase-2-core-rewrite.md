# Phase 2: Core Rewrite — resolve_model + load_merged_aliases

## Scope

Rewrite `resolve_model()` in `models.py` to use `_run_mars_models_resolve()` as primary resolution, with `pattern_fallback_harness()` for raw model IDs. Simplify `load_merged_aliases()` to stop calling `_resolve_alias_harness()`. Update `AliasEntry.harness` property fallback.

**This phase fixes the live bug:** the resolved `model_id` (not the alias name) is returned by `resolve_model()`, so downstream code that calls `str(resolved.model_id)` gets `"gpt-5.3-codex"` instead of `"codex"`.

## Files to Modify

- `src/meridian/lib/catalog/models.py` — rewrite `resolve_model()`, simplify `load_merged_aliases()`, delete `_resolve_alias_harness()`
- `src/meridian/lib/catalog/model_aliases.py` — update `AliasEntry.harness` property fallback

## What to Build

### `resolve_model()` in `models.py` — NEW BEHAVIOR

Replace the current implementation with mars-first resolution. Mars is always present — if the binary is missing, that's a hard error (not a fallback trigger).

```python
def resolve_model(name_or_alias: str, repo_root: Path | None = None) -> AliasEntry:
    """Resolve alias to model id, or pass through a direct model identifier.

    Resolution: mars resolve → pattern fallback for raw model IDs → hard error.
    Mars is always present (bundled with meridian).
    """
    from meridian.lib.catalog.model_aliases import _run_mars_models_resolve

    normalized = name_or_alias.strip()
    if not normalized:
        raise ValueError("Model identifier must not be empty.")

    # Step 1: Try mars resolve (alias + harness in one call)
    mars_result = _run_mars_models_resolve(normalized, repo_root)
    if mars_result is not None:
        model_id = mars_result.get("model_id")
        harness = mars_result.get("harness")
        harness_source = mars_result.get("harness_source", "")

        if isinstance(model_id, str) and model_id.strip():
            resolved_harness: HarnessId | None = None
            if isinstance(harness, str) and harness.strip():
                try:
                    resolved_harness = HarnessId(harness.strip())
                except ValueError:
                    pass  # Unknown harness string → treat as None, fall through

            if harness_source == "unavailable":
                candidates = mars_result.get("harness_candidates", [])
                candidate_list = candidates if isinstance(candidates, list) else []
                raise ValueError(
                    f"No installed harness for model '{normalized}'. "
                    f"Install one of: {', '.join(str(c) for c in candidate_list)}"
                )

            if resolved_harness is None:
                # Mars resolved the alias but didn't provide harness → pattern fallback
                resolved_harness = pattern_fallback_harness(model_id.strip())

            return AliasEntry(
                alias=str(mars_result.get("name", "") or ""),
                model_id=ModelId(model_id.strip()),
                resolved_harness=resolved_harness,
                description=str(mars_result.get("description", "") or "") or None,
            )

    # Step 2: Raw model ID → pattern-based harness fallback
    resolved_harness = pattern_fallback_harness(normalized)
    return AliasEntry(alias="", model_id=ModelId(normalized), resolved_harness=resolved_harness)
```

Import `pattern_fallback_harness` from `model_policy` (add to the existing import block from `model_policy`).

### `load_merged_aliases()` in `models.py` — SIMPLIFY

Remove the `_resolve_alias_harness()` call. Mars already provides harness info in its list output. The existing `_mars_list_to_entries()` in `model_aliases.py` already parses the harness field from mars list output — it's `_resolve_alias_harness` that was redundantly re-routing.

```python
def load_merged_aliases(repo_root: Path | None = None) -> list[AliasEntry]:
    """Load model aliases from mars packages."""
    resolved_root = resolve_repo_root(repo_root) if repo_root is not None else None
    return load_mars_aliases(resolved_root)
```

### Delete `_resolve_alias_harness()` from `models.py`

Remove the entire function (lines 91-96). It's no longer called.

### `AliasEntry.harness` property in `model_aliases.py` — UPDATE FALLBACK

Change the import and the fallback call:

**Current:**
```python
from meridian.lib.catalog.model_policy import DEFAULT_HARNESS_PATTERNS, route_model_with_patterns
# ...
    @property
    def harness(self) -> HarnessId:
        if self.resolved_harness is not None:
            return self.resolved_harness
        return route_model_with_patterns(
            str(self.model_id),
            patterns_by_harness=DEFAULT_HARNESS_PATTERNS,
        ).harness_id
```

**New:**
```python
from meridian.lib.catalog.model_policy import pattern_fallback_harness
# ...
    @property
    def harness(self) -> HarnessId:
        if self.resolved_harness is not None:
            return self.resolved_harness
        return pattern_fallback_harness(str(self.model_id))
```

Remove the `DEFAULT_HARNESS_PATTERNS` and `route_model_with_patterns` imports from `model_aliases.py` (they're no longer used there).

## Dependencies

- Requires: Phase 1 (`pattern_fallback_harness`, `_run_mars_models_resolve`)
- Independent of: Phase 3, Phase 4

## Constraints

- `resolve_model()` return type stays `AliasEntry` — no signature change
- `load_merged_aliases()` return type stays `list[AliasEntry]` — no signature change
- `resolve_alias()` continues to work (it calls `load_merged_aliases` internally)
- The `_PROVIDER_TO_HARNESS` dict in `models.py` is NOT touched — it's for discovery, not routing (Decision D8)

## Verification Criteria

- [ ] `uv run pyright` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] `resolve_model("opus")` returns `AliasEntry(model_id=ModelId("claude-opus-4-6"), ...)` — the model_id is the concrete ID, not "opus"
- [ ] `resolve_model("claude-opus-4-6")` works via pattern fallback (not an alias)
- [ ] `resolve_model("")` raises ValueError
