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

## New Flow — Three-Step Fallback

```
User: -m opus
  Step 1: mars models resolve opus --json
  → {"model_id": "claude-opus-4-6", "harness": "claude", "harness_source": "auto_detected", ...}
  → AliasEntry(model_id="claude-opus-4-6", resolved_harness=CLAUDE)
```

When mars binary is unavailable (not installed, timeout, crash):
```
User: -m opus (mars unavailable)
  Step 1: mars models resolve → fails
  Step 2: _read_mars_merged_file() → finds "opus" → pinned alias with model_id + optional harness
  → AliasEntry(model_id="claude-opus-4-6", resolved_harness=CLAUDE or None)
  → If resolved_harness is None, pattern_fallback_harness("claude-opus-4-6") → CLAUDE
```

When mars is unavailable AND model isn't a known alias:
```
User: -m claude-opus-4-6 (mars unavailable, not in merged file)
  Step 1: mars models resolve → fails
  Step 2: merged file lookup → not found
  Step 3: pattern_fallback_harness("claude-opus-4-6") → matches "claude-*" → CLAUDE
```

When nothing matches:
```
User: -m some-unknown-model (mars unavailable, no alias, no pattern match)
  Step 1: mars → fails
  Step 2: merged file → not found
  Step 3: pattern_fallback_harness → no match → ValueError
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
            # Mars found the model. Handle harness availability.
            resolved_harness: HarnessId | None = None
            if isinstance(harness, str) and harness.strip():
                try:
                    resolved_harness = HarnessId(harness.strip())
                except ValueError:
                    pass  # Unknown harness string → treat as None, fall through

            if harness_source == "unavailable":
                # Mars knows the model but no harness is installed.
                # Hard error regardless of whether mars returned a harness string —
                # an unavailable harness won't work even if named.
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

    # Step 2: Mars unavailable — try cached merged aliases
    merged = _read_mars_merged_file(repo_root)
    if merged:
        entries = _mars_merged_to_entries(merged)
        match = load_alias_by_name(normalized, entries)
        if match is not None:
            if match.resolved_harness is None:
                # Cached alias without harness → pattern fallback for harness
                resolved = pattern_fallback_harness(str(match.model_id))
                match = match.model_copy(update={"resolved_harness": resolved})
            return match

    # Step 3: Raw model ID → pattern-based harness fallback
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
3. If only model is set, derives harness from model (now via mars → cached alias → pattern)
4. If model is set at higher precedence than harness, model-derived harness wins

The only change is *how* harness is derived from model — three-step fallback instead of pattern-only.

## `harness: null` / Unavailable Handling

When mars resolves a model but signals `harness_source: "unavailable"`:

**Behavior:** Hard error with actionable message. If mars knows the model exists but has no installed harness for it, the user needs to install a harness, not silently fall through to pattern matching (which would pick a harness family that isn't installed either).

**Error format:** `"No installed harness for model 'opus'. Install one of: claude, opencode"`

This is distinct from mars being *unavailable* (binary not found / timeout), where fallback to cached aliases and patterns is correct.

## `mars models resolve` Input Semantics

`mars models resolve` accepts alias names. When given a name not in the alias registry, it returns exit code 1. This is correct — meridian's fallback chain handles unknown inputs via steps 2 and 3.

Direct model IDs (e.g., `claude-opus-4-6`) may or may not be in mars's alias registry. If not, they fall through to pattern matching, which is the right behavior — mars doesn't need to echo back direct model IDs.

## Error Handling Summary

| Scenario | Step 1 (mars resolve) | Step 2 (cached aliases) | Step 3 (patterns) | Result |
|---|---|---|---|---|
| Known alias, harness installed | Returns model_id + harness | — | — | Success |
| Known alias, no harness installed | Returns model_id, harness_source=unavailable | — | — | **Hard error** with candidates |
| Known alias, mars unavailable | Fails | Found in merged file | — | Success |
| Unknown alias, known model pattern, mars unavailable | Fails | Not found | Pattern match | Success |
| Unknown input everywhere | Fails | Not found | No match | ValueError |
| Mars returns unknown HarnessId string | harness parse fails | — | Pattern fallback | Success |
