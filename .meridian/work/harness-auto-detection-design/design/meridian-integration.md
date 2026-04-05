# Meridian Integration

## Current State

Meridian already handles harness resolution gracefully when mars doesn't provide one:

1. **`model_aliases.py`**: `AliasEntry.harness` property falls back to `route_model_with_patterns()` when `resolved_harness` is `None`.
2. **`model_policy.py`**: `DEFAULT_HARNESS_PATTERNS` maps model ID patterns to harnesses (e.g., `claude-*` → claude harness).
3. **`resolve.py`**: `resolve_policies()` has a full fallback chain: explicit harness → profile harness → model-based routing → config default.

This means **meridian needs minimal changes**. The main improvement is consuming the richer mars resolve output.

## Changes to `model_aliases.py`

### `_mars_list_to_entries` — Consume new fields

The `mars models list --json` output now includes `provider` and `harness_source`. Meridian should:

1. **Use `harness`** from mars JSON when present (already does this).
2. **Log `harness_source`** for debugging when it's `"auto-detected"` vs `"explicit"`.
3. **Skip aliases where `harness` is `null`** — same as current behavior (skips aliases without `resolved_model`), but now also skip aliases where no harness is available.

```python
def _mars_list_to_entries(aliases_list: list[dict[str, object]]) -> list[AliasEntry]:
    entries: list[AliasEntry] = []
    for item in aliases_list:
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        resolved_model = item.get("resolved_model") or item.get("model_id")
        harness = item.get("harness")
        description = item.get("description")

        # Skip unresolved or harness-unavailable aliases
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            continue
        # harness=null means no installed harness — skip
        if harness is not None and not isinstance(harness, str):
            continue

        entries.append(entry(
            alias=name.strip(),
            model_id=resolved_model.strip(),
            harness=str(harness) if isinstance(harness, str) else None,
            description=str(description) if isinstance(description, str) else None,
        ))
    return entries
```

### `_mars_merged_to_entries` — Handle missing harness

The `models-merged.json` file may now have aliases without a `harness` field. These should still be loaded — meridian's routing handles the harness fallback.

No change needed here — the code already treats `harness` as optional (`harness = typed_data.get("harness")`).

## Changes to `resolve.py`

### No changes needed

The `resolve_policies` function already handles the full fallback chain. When mars provides a harness, it flows through `AliasEntry.resolved_harness`. When mars doesn't, `AliasEntry.harness` property falls back to `model_policy.py` routing.

The existing code in `resolve_harness()` and `resolve_policies()` is already correct for the new behavior.

## Potential Future: Direct `mars models resolve` Call

Currently meridian calls `mars models list --json` and filters. A future optimization could call `mars models resolve <alias> --json` for single-alias resolution (faster — resolves one alias instead of all).

This is NOT part of this design — the current approach works and changing the call pattern is a separate optimization. But the mars resolve API is designed to support this use case.

## Summary of Meridian Changes

| File | Change | Risk |
|------|--------|------|
| `model_aliases.py` | Handle `model_id` field name in mars JSON (alongside existing `resolved_model`) | Low — additive |
| `model_aliases.py` | Skip aliases with `harness: null` | Low — already skips unresolved |
| Everything else | No changes | None |

The key insight is that meridian's existing `model_policy.py` routing is the **correct fallback** for harness resolution. Mars adding auto-detection is an improvement to the mars-side experience (better `mars models list` output, `mars harness list` diagnostics), but meridian doesn't depend on it — it already handles the case.
