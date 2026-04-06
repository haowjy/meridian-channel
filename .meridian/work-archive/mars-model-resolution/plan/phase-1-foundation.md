# Phase 1: Foundation — New Resolution Primitives

## Scope

Add the two new functions that Phase 2 depends on: `pattern_fallback_harness()` in `model_policy.py` and `_run_mars_models_resolve()` in `model_aliases.py`. These are additive — no existing code changes, no callers yet.

## Files to Modify

- `src/meridian/lib/catalog/model_policy.py` — add `pattern_fallback_harness()`
- `src/meridian/lib/catalog/model_aliases.py` — add `_run_mars_models_resolve()`

## What to Build

### `pattern_fallback_harness()` in `model_policy.py`

A simplified version of `route_model_with_patterns()` that uses only `DEFAULT_HARNESS_PATTERNS` (no user config merge). This is the last-resort fallback for raw model IDs that aren't mars aliases.

```python
def pattern_fallback_harness(model: str) -> HarnessId:
    """Route a raw model ID to a harness using DEFAULT_HARNESS_PATTERNS only.

    Used when mars doesn't recognize the input (not an alias) and we need
    to infer the harness from the model ID string pattern.

    Raises ValueError if no pattern matches.
    """
    normalized = model.strip()
    matched_harnesses = [
        harness
        for harness, patterns in DEFAULT_HARNESS_PATTERNS.items()
        if any(match_pattern(pattern, normalized) for pattern in patterns)
    ]
    if len(matched_harnesses) == 1:
        return matched_harnesses[0]
    if len(matched_harnesses) > 1:
        joined = ", ".join(str(h) for h in matched_harnesses)
        raise ValueError(
            f"Model '{model}' matches multiple harness patterns: {joined}."
        )
    raise ValueError(f"Unknown model '{model}'. No harness pattern matches.")
```

Note: `match_pattern()` already exists and is used by visibility. Reuse it.

### `_run_mars_models_resolve()` in `model_aliases.py`

Calls `mars models resolve <name> --json`. Follows the exact same subprocess pattern as the existing `_run_mars_models_list()`.

```python
def _run_mars_models_resolve(name: str, repo_root: Path | None = None) -> dict[str, object] | None:
    """Call ``mars models resolve <name> --json`` and return the resolved entry.

    Returns None when mars binary is unavailable, the command fails,
    or the alias is unknown (exit code 1). The caller distinguishes
    "mars doesn't know this alias" from "mars is broken" by checking
    whether the mars binary exists separately.
    """
    mars_bin = _resolve_mars_binary()
    if mars_bin is None:
        return None
    cmd = [mars_bin, "models", "resolve", name, "--json"]
    if repo_root is not None:
        cmd.extend(["--root", str(repo_root)])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
```

## Dependencies

- Requires: nothing (additive only)
- Independent of: all other phases

## Constraints

- Do NOT modify any existing function signatures or behavior
- Do NOT add callers yet — Phase 2 wires these up
- `_run_mars_models_resolve` is a private function (underscore prefix) — it's internal to the module

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes (no existing tests break)
- [ ] Both functions are importable: `from meridian.lib.catalog.model_policy import pattern_fallback_harness`
