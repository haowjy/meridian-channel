# `ensure_fresh` — The Refresh Helper

All cache freshness logic lives in one function in `src/models/mod.rs`:

```rust
pub enum RefreshMode {
    /// Refresh if missing or stale; no-op if fresh.
    Auto,
    /// Refresh unconditionally. Used by `mars models refresh`.
    Force,
    /// Never hit the network; return whatever's on disk. May be empty/stale.
    Offline,
}

pub enum RefreshOutcome {
    /// Cache was already fresh; no network call.
    AlreadyFresh,
    /// Cache was refreshed successfully from the API.
    Refreshed { models_count: usize },
    /// Fetch failed, returning stale cache on disk.
    StaleFallback { reason: String },
    /// Offline mode, returning whatever's on disk (may be empty).
    Offline,
}

pub fn ensure_fresh(
    mars_dir: &Path,
    ttl_hours: u32,
    mode: RefreshMode,
) -> Result<(ModelsCache, RefreshOutcome), MarsError>;
```

The function returns both the cache *and* a structured outcome so callers can
decide how loudly to surface each path (e.g. `mars models refresh` prints
"Cached N models" on `Refreshed`; `mars sync` stays silent on `AlreadyFresh`
but warns on `StaleFallback`).

## Flow

```
enter ensure_fresh(mode)
  |
  | apply MARS_OFFLINE coercion: if env set, mode := Offline
  v
read_cache_if_exists()  --> (cache_opt, is_fresh)
  |
  +-- mode == Offline ------> return (cache_opt.unwrap_or_empty, Offline)
  |                              (if cache_opt is None and caller needs
  |                               models, caller surfaces hard error)
  |
  +-- mode == Auto && is_fresh --> return (cache, AlreadyFresh)
  |
  +-- mode == Auto && !is_fresh ---\
  +-- mode == Force ---------------+-> do_refresh(cache_opt)
                                   /
do_refresh(prior):
  acquire FileLock on .mars/.models-cache.lock
  re-read cache under lock (another process may have just refreshed)
  if mode == Auto and now fresh:
      return (cache, Refreshed{count=0})   -- "someone else did it"
  attempt fetch_models()
    on success:
      write_cache({ models, fetched_at: now })
      return (cache, Refreshed{count})
    on failure:
      if prior cache has models:
        warn("models cache refresh failed: {err}; using stale cache")
        return (prior, StaleFallback{reason})
      else:
        return Err(MarsError::ModelCacheUnavailable{cause: err})
```

The "re-read under lock" step is the key correctness guard: the first
caller into a concurrent burst fetches; every subsequent caller wakes up,
sees the fresh timestamp, and returns immediately without repeating the
network round-trip.

## MARS_OFFLINE Coercion

`ensure_fresh` checks `MARS_OFFLINE` exactly once, at the top of the
function, and downgrades `Auto`/`Force` to `Offline`. This is deliberate:
centralizing the env check means every call site inherits the opt-out for
free — callers don't have to thread a boolean through. The `--no-refresh-
models` CLI flag sets `MARS_OFFLINE=1` in the process env before dispatch
(see `call-sites.md`), so both opt-outs collapse to one code path.

Note: `mars models refresh` is a special case. It calls `ensure_fresh(Force)`
but suppresses the env coercion by passing a `force_ignore_offline: bool`
parameter — or, equivalently, calls `fetch_models` + `write_cache` directly
with its own lock acquisition. The design picks the second route: `mars
models refresh` bypasses `ensure_fresh` entirely, using the same lock
primitive but always fetching. This keeps `ensure_fresh`'s contract
simple — if mode is `Offline`, never fetches. Period.

## Error Types

Add to `MarsError`:

```rust
#[error("models cache is empty and refresh is disabled ({reason}). \
         Run `mars models refresh` or unset MARS_OFFLINE.")]
ModelCacheUnavailable { reason: String },
```

`reason` is one of:
- `"MARS_OFFLINE is set"` when env was the trigger
- `"--no-refresh-models flag"` when the flag was the trigger
- `"fetch failed: <err>"` when the network call failed and no prior cache
  existed

## What `ensure_fresh` Does *Not* Do

- It does not decide *which* caller gets to print status output. Callers
  inspect `RefreshOutcome` and choose their own verbosity.
- It does not cache results in-process. Every call re-reads from disk. This
  keeps state authoritative (see project principle #2: Files as Authority)
  and simplifies test setup.
- It does not retry fetch failures. One attempt, then fall back.
- It does not touch `models-merged.json`. That's sync's concern.
