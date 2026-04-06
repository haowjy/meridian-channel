# Resolution Flow (After)

## Current Flow

```
User: -m opus
  → load_merged_aliases() → find "opus" → AliasEntry(model_id="claude-opus-4-6", resolved_harness=None)
  → _resolve_alias_harness() → route_model("claude-opus-4-6") → pattern match "claude-*" → HarnessId.CLAUDE
  → AliasEntry(model_id="claude-opus-4-6", resolved_harness=CLAUDE)
```

For unknown models (not an alias, not matching patterns):
```
User: -m some-new-model
  → load_merged_aliases() → not found
  → route_model("some-new-model") → no pattern match → ValueError
```

## New Flow — Mars as Authority

Mars is always present (bundled with meridian). No offline/cached fallback needed.

```
User: -m opus
  Step 1: mars models resolve opus --json
  → {"model_id": "claude-opus-4-6", "harness": "claude", "harness_source": "auto_detected", ...}
  → AliasEntry(model_id="claude-opus-4-6", resolved_harness=CLAUDE)
```

When model isn't a mars alias (raw model ID):
```
User: -m claude-opus-4-6
  Step 1: mars models resolve → exit 1 (unknown alias)
  Step 2: pattern_fallback_harness("claude-opus-4-6") → matches "claude-*" → CLAUDE
```

When nothing matches:
```
User: -m some-unknown-model
  Step 1: mars → exit 1
  Step 2: pattern_fallback_harness → no match → ValueError
```

When mars itself errors (binary broken, unexpected failure):
```
User: -m opus (mars broken)
  Step 1: mars → subprocess error
  → Real error: "Mars model resolution failed. Run 'meridian doctor' to diagnose."
```

## `resolve_model()` — The Core Change

Current signature and behavior in `models.py`:

```python
def resolve_model(name_or_alias: str, repo_root: Path | None = None) -> AliasEntry:
    # 1. Try alias lookup from mars
    resolved = load_alias_by_name(normalized, load_merged_aliases(repo_root))
    if resolved is not None:
        _ = route_model(str(resolved.model_id))  # validate harness exists
        return resolved
    # 2. Fallback: treat as raw model ID, route via patterns
    resolved_harness = route_model(normalized).harness_id
    return AliasEntry(alias="", model_id=ModelId(normalized), resolved_harness=resolved_harness)
```

New behavior:

```python
def resolve_model(name_or_alias: str, repo_root: Path | None = None) -> AliasEntry:
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
                raise ValueError(
                    f"No installed harness for model '{normalized}'. "
                    f"Install one of: {', '.join(candidates)}"
                )

            if resolved_harness is None:
                # Mars resolved the model but didn't provide harness → pattern fallback
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

## `_derive_harness_from_model()` — Simplified

Currently in `resolve.py`, this is called when no layer sets harness explicitly:

```python
def _derive_harness_from_model(model_str: str, *, repo_root: Path) -> HarnessId:
    try:
        resolved = resolve_model(model_str, repo_root=repo_root)
        return resolved.harness
    except ValueError:
        decision = route_model(model_str, mode="harness", repo_root=repo_root)
        return decision.harness_id
```

After the change, `resolve_model()` already handles all fallback cases, so:

```python
def _derive_harness_from_model(model_str: str, *, repo_root: Path) -> HarnessId:
    resolved = resolve_model(model_str, repo_root=repo_root)
    return resolved.harness
```

## `resolve_harness()` — Compatibility Check

This function validates that an explicit `--harness` override is compatible with the model. It stays, but uses `resolve_model()` instead of `route_model()`:

```python
def resolve_harness(*, model, harness_override, harness_registry, repo_root) -> HarnessId:
    resolved = resolve_model(str(model), repo_root=repo_root)
    routed_harness_id = resolved.harness
    # ... rest of compatibility check unchanged
```

## Precedence Interaction

The precedence algorithm in `resolve_policies()` doesn't change. It still:
1. Merges layers (CLI > env > profile > config)
2. If harness is set explicitly, uses it
3. If only model is set, derives harness from model (now via mars → pattern)
4. If model is set at higher precedence than harness, model-derived harness wins

The only change is *how* harness is derived from model — mars first, pattern fallback for raw IDs.

## `harness: null` / Unavailable Handling

When mars resolves a model but signals `harness_source: "unavailable"`:

**Behavior:** Hard error with actionable message. If mars knows the model exists but has no installed harness for it, the user needs to install a harness.

**Error format:** `"No installed harness for model 'opus'. Install one of: claude, opencode"`

## Error Handling Summary

| Scenario | Step 1 (mars resolve) | Step 2 (patterns) | Result |
|---|---|---|---|
| Known alias, harness installed | Returns model_id + harness | — | Success |
| Known alias, no harness installed | Returns model_id, harness_source=unavailable | — | **Hard error** with candidates |
| Raw model ID, pattern matches | Exit 1 | Pattern match | Success |
| Unknown input everywhere | Exit 1 | No match | ValueError |
| Mars binary broken | Subprocess error | — | **Hard error**: run meridian doctor |
| Mars returns unknown HarnessId string | harness parse fails | Pattern fallback | Success |
