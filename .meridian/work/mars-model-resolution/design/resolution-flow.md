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

## New Flow

```
User: -m opus
  → mars models resolve opus --json
  → {"model_id": "claude-opus-4-6", "harness": "claude", ...}
  → AliasEntry(model_id="claude-opus-4-6", resolved_harness=CLAUDE)
```

For unknown models (mars doesn't know it either):
```
User: -m some-new-model
  → mars models resolve some-new-model --json → exit code 1 (unknown alias)
  → fallback: DEFAULT_HARNESS_PATTERNS pattern match → HarnessId or ValueError
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
    # 1. Try mars resolve (single call replaces alias lookup + harness routing)
    mars_result = _run_mars_models_resolve(normalized, repo_root)
    if mars_result is not None:
        model_id = mars_result.get("model_id")
        harness = mars_result.get("harness")
        if model_id:
            return AliasEntry(
                alias=mars_result.get("name", ""),
                model_id=ModelId(model_id),
                resolved_harness=HarnessId(harness) if harness else None,
                description=mars_result.get("description"),
            )

    # 2. Fallback: pattern-based routing (mars unavailable or model unknown to mars)
    resolved_harness = _pattern_route(normalized)
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

After the change, `resolve_model()` already handles both cases (mars resolve + pattern fallback), so this simplifies to:

```python
def _derive_harness_from_model(model_str: str, *, repo_root: Path) -> HarnessId:
    resolved = resolve_model(model_str, repo_root=repo_root)
    return resolved.harness
```

## `resolve_harness()` — Compatibility Check

This function validates that an explicit `--harness` override is compatible with the model. It stays, but instead of calling `route_model()` it calls `resolve_model()`:

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
3. If only model is set, derives harness from model (now via mars)
4. If model is set at higher precedence than harness, model-derived harness wins

The only change is *how* harness is derived from model — mars instead of patterns.

## Error Handling

| Scenario | Before | After |
|---|---|---|
| Mars not installed | Pattern fallback | Pattern fallback (same) |
| Mars resolve fails (timeout, crash) | N/A | Pattern fallback |
| Unknown alias, known model pattern | Pattern match | Mars resolve → miss → pattern match |
| Unknown alias, unknown model | ValueError | Mars resolve → miss → pattern → ValueError |
| Known alias, no installed harness | Works (harness from patterns) | Works (harness from mars, may be null → pattern fallback) |
