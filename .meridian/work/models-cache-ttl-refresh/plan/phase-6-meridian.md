# Phase 6: Meridian-Channel Integration

**Repo:** meridian-channel
**Depends on:** Phase 5 (mars changes published / available locally)
**Est. size:** ~10 LoC + smoke doc

## Goal

Make sure meridian spawns benefit from `ensure_fresh(Auto)` without
introducing any new refresh logic on meridian's side. The only code
change is raising the `mars models resolve` / `mars models list`
subprocess timeout to accommodate a cold fetch.

## Files

- `src/meridian/lib/catalog/model_aliases.py`
  - Raise the `subprocess.run(..., timeout=10)` argument to `60` in
    `_run_mars_models_list` and `run_mars_models_resolve`.
  - Add a short comment explaining the generous timeout ("mars may
    perform a cold models.dev fetch inside `ensure_fresh(Auto)`").
- `tests/smoke/` — add a markdown file `models-cache-auto-refresh.md`
  describing the user-level scenario (see below).

## Implementation

```python
# In _run_mars_models_list:
# 60s accommodates a cold `ensure_fresh(Auto)` fetch inside mars;
# resolution is launch-critical, so we'd rather wait than fail spawns.
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

# In run_mars_models_resolve: same, with the same comment.
```

No structural changes, no new functions, no new config knobs.

## Smoke Test: `tests/smoke/models-cache-auto-refresh.md`

```markdown
# Smoke: Models Cache Auto-Refresh

Verifies that `meridian spawn` triggers mars's automatic models-cache
refresh when the cache is empty or stale, and that `MARS_OFFLINE=1`
produces a clean error instead of a hang.

## Setup

1. Pick a project with at least one mars-managed agent that uses an
   alias you know maps to a provider covered by the models cache (e.g.
   an Anthropic alias).
2. `rm -f .mars/models-cache.json` to force a cold state.

## Case 1: Cold cache, spawn succeeds

```bash
meridian spawn -a <alias-agent> -p "echo hello"
```

**Expected:** spawn succeeds. `.mars/models-cache.json` now exists with a
recent `fetched_at`.

## Case 2: Stale cache, spawn still succeeds

```bash
# Hand-edit .mars/models-cache.json and set fetched_at to an old value,
# e.g. 1 (Unix epoch + 1 sec).
meridian spawn -a <alias-agent> -p "echo hello"
```

**Expected:** spawn succeeds, cache `fetched_at` is now recent.

## Case 3: Empty cache, offline, spawn fails cleanly

```bash
rm -f .mars/models-cache.json
MARS_OFFLINE=1 meridian spawn -a <alias-agent> -p "echo hello"
```

**Expected:** spawn fails fast with a clear error message mentioning
`mars models refresh` and `MARS_OFFLINE`. No 60-second hang.

## Case 4: Fresh cache, offline, spawn succeeds

```bash
# Ensure cache is fresh first.
mars models refresh
MARS_OFFLINE=1 meridian spawn -a <alias-agent> -p "echo hello"
```

**Expected:** spawn succeeds using the cached catalog; no network
traffic.

## Case 5: Concurrent spawns

```bash
rm -f .mars/models-cache.json
meridian spawn -a <alias-agent> -p "echo 1" &
meridian spawn -a <alias-agent> -p "echo 2" &
meridian spawn -a <alias-agent> -p "echo 3" &
wait
```

**Expected:** all three spawns succeed. Only one network fetch observed
(verify via `mars_dir/models-cache.json` mtime and/or by watching
network activity).
```

## Verification

- `uv run pyright` → 0 errors.
- `uv run ruff check .`
- Manual execution of the smoke scenarios above.

## Out of Scope

- Touching `src/meridian/lib/catalog/models.py`'s `_CACHE_TTL_SECONDS` /
  `models.json` discovery cache. That's a separate meridian-internal
  cache used by the `meridian models` UI, not by spawn-time resolution.
  Follow-up work item if/when needed.
- Adding meridian-side config for the mars TTL.
- Adding meridian CLI flags for `--no-refresh-models`. Users pass
  `MARS_OFFLINE=1` on the meridian invocation; the env var flows through
  `subprocess.run` to mars.
