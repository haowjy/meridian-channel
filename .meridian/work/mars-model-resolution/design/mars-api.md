# Mars API Contract

## Required: `mars models resolve <name> --json`

Mars already has `mars models resolve` (see `cli/models.rs` `run_resolve()`). Its JSON output includes:

```json
{
  "name": "opus",
  "model_id": "claude-opus-4-6",
  "provider": "Anthropic",
  "harness": "claude",
  "harness_source": "auto_detected",
  "harness_candidates": ["claude", "opencode"],
  "spec": { "mode": "auto-resolve", ... },
  "description": "..."
}
```

This is exactly what meridian needs. The key fields:
- `model_id` — concrete model identifier to pass to the harness
- `harness` — resolved harness name (may be null if no installed harness found)
- `harness_source` — `"explicit"` (from alias config), `"auto_detected"` (from provider preference + installed CLIs), or `"unavailable"`
- `harness_candidates` — which harnesses *could* run this model (for error messages)

## Existing: `mars models list --json`

Already called by `_run_mars_models_list()` in `model_aliases.py`. Returns all aliases with the same fields. Used for bulk listing in `meridian models list`.

## Fallback: `.mars/models-merged.json`

Already read by `_read_mars_merged_file()` when mars binary is unavailable. Contains pinned aliases with optional `harness` field. Auto-resolve aliases can't be resolved without the cache, so those are skipped.

## Integration Pattern

Meridian already has `_resolve_mars_binary()` and `_run_mars_models_list()` in `model_aliases.py`. The new `mars models resolve` call follows the same pattern:

```python
def _run_mars_models_resolve(name: str, repo_root: Path | None = None) -> dict[str, object] | None:
    """Call ``mars models resolve <name> --json`` and return the resolved entry."""
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

## Input Semantics

`mars models resolve` accepts **alias names only** (e.g., `opus`, `sonnet`, `codex`). When given a name not in the alias registry, it returns exit code 1 with an error JSON:

```json
{"error": "unknown alias: some-name"}
```

Direct model IDs (e.g., `claude-opus-4-6`) are not handled by mars resolve — they fall through to meridian's pattern fallback. This is intentional: mars owns alias→model mapping; meridian owns raw-model-ID→harness via hardcoded patterns.

## Error Cases and Exit Codes

| Scenario | Exit code | Output |
|---|---|---|
| Alias found, harness installed | 0 | Full resolved JSON |
| Alias found, no harness installed | 0 | JSON with `harness_source: "unavailable"`, `harness: null` or explicit |
| Alias found, no models cache | 0 (pinned) / 1 (auto-resolve) | JSON or error |
| Unknown alias | 1 | `{"error": "unknown alias: ..."}` |

## What Mars Does NOT Own

Mars does not know about:
- Meridian's precedence layers (CLI > env > profile > config)
- Meridian's harness registry (which harnesses are registered as adapters)
- Harness-specific model defaults (`config.default_model_for_harness()`)
- Whether a harness supports primary launch

These remain meridian's responsibility.
