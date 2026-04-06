# Phase 2: `ensure_fresh` Helper

**Repo:** mars-agents
**Depends on:** Phase 1 (uses `Settings::models_cache_ttl_hours`)
**Est. size:** ~180 LoC + unit tests

## Goal

Introduce the single helper that centralizes refresh policy, concurrency,
and fallback. After this phase, nothing uses it yet — phases 3 and 4 wire
it in.

## Files

- `src/models/mod.rs`
  - Add `RefreshMode`, `RefreshOutcome` enums.
  - Add `ensure_fresh` function.
  - Add shared helpers `resolve_refresh_mode(no_refresh_flag: bool)`
    and `load_models_cache_ttl(ctx: &MarsContext)`.
  - Rename `cli::models::now_iso` → `models::now_unix_secs` and move it
    into `models/mod.rs` (drive-by: current name lies).
  - Update the existing `run_refresh` caller in `cli/models.rs` to use
    the renamed helper.
- `src/error.rs` — add `ModelCacheUnavailable { reason: String }` variant
  with `thiserror` message per `design/ensure-fresh.md`.

## Implementation Notes

### Freshness computation

```rust
fn is_fresh(cache: &ModelsCache, ttl_hours: u32) -> bool {
    if ttl_hours == 0 {
        return false;
    }
    let Some(fetched_str) = &cache.fetched_at else {
        return false;
    };
    let Ok(fetched) = fetched_str.parse::<u64>() else {
        return false; // unparseable — treat as stale
    };
    let now = now_unix_secs_value();
    if fetched > now {
        return false; // clock skew / future timestamp — treat as stale
    }
    (now - fetched) < (ttl_hours as u64) * 3600
}
```

Provide both `now_unix_secs() -> String` (for writing `fetched_at`) and
`now_unix_secs_value() -> u64` (for comparisons). The first is a thin
wrapper around the second.

### Lock + double-check

```rust
let cache_path = mars_dir.join(CACHE_FILE);
let lock_path = mars_dir.join(".models-cache.lock");
std::fs::create_dir_all(mars_dir)?;

// First read, outside the lock.
let prior = read_cache(mars_dir)?;
if mode != RefreshMode::Force && is_fresh(&prior, ttl_hours) {
    return Ok((prior, RefreshOutcome::AlreadyFresh));
}

// MARS_OFFLINE coercion.
let effective_mode = if std::env::var_os("MARS_OFFLINE").is_some() {
    RefreshMode::Offline
} else {
    mode
};

if matches!(effective_mode, RefreshMode::Offline) {
    if prior.models.is_empty() && prior.fetched_at.is_none() {
        return Err(MarsError::ModelCacheUnavailable {
            reason: "MARS_OFFLINE is set".to_string(),
        });
    }
    return Ok((prior, RefreshOutcome::Offline));
}

let _guard = crate::fs::FileLock::acquire(&lock_path)?;

// Re-check under the lock: another process may have just refreshed.
let under_lock = read_cache(mars_dir)?;
if effective_mode == RefreshMode::Auto && is_fresh(&under_lock, ttl_hours) {
    return Ok((under_lock, RefreshOutcome::Refreshed { models_count: 0 }));
}

// We own the fetch.
match fetch_models() {
    Ok(models) => {
        let count = models.len();
        let cache = ModelsCache {
            models,
            fetched_at: Some(now_unix_secs()),
        };
        write_cache(mars_dir, &cache)?;
        Ok((cache, RefreshOutcome::Refreshed { models_count: count }))
    }
    Err(err) => {
        if !under_lock.models.is_empty() {
            Ok((
                under_lock,
                RefreshOutcome::StaleFallback {
                    reason: format!("{err}"),
                },
            ))
        } else {
            Err(MarsError::ModelCacheUnavailable {
                reason: format!("fetch failed: {err}"),
            })
        }
    }
}
```

### Helpers

```rust
pub fn resolve_refresh_mode(no_refresh_flag: bool) -> RefreshMode {
    if no_refresh_flag {
        RefreshMode::Offline
    } else {
        RefreshMode::Auto
    }
}

pub fn load_models_cache_ttl(ctx: &MarsContext) -> u32 {
    crate::config::load(&ctx.project_root)
        .map(|c| c.settings.models_cache_ttl_hours)
        .unwrap_or(24)
}
```

`resolve_refresh_mode` does not itself check `MARS_OFFLINE` — it only
handles the CLI flag. The env check lives inside `ensure_fresh` so that
*any* future caller (not just CLI handlers) inherits the opt-out.

### `run_refresh` adjustment

Update `cli/models.rs::run_refresh` to acquire the lock and use
`now_unix_secs()` from `models/` instead of the old local helper. It
still bypasses `ensure_fresh` entirely (see `design/call-sites.md` §4).

## Unit Tests

All tests use `tempfile::tempdir` for a temporary `.mars` dir and call
`ensure_fresh` directly.

1. **Missing cache, offline** → `ModelCacheUnavailable`.
2. **Missing cache, auto, fetch mocked to fail** → `ModelCacheUnavailable`.
3. **Stale cache, offline** → returns stale, `RefreshOutcome::Offline`.
4. **Fresh cache, auto** → no fetch, `AlreadyFresh`.
5. **Stale cache, auto, fetch mocked to succeed** → returns new cache,
   `Refreshed`.
6. **Stale cache, auto, fetch fails** → returns stale cache,
   `StaleFallback`.
7. **TTL = 0, auto** → every call refreshes.
8. **`fetched_at` unparseable** → treated as stale.
9. **`fetched_at` in future** → treated as stale.
10. **`MARS_OFFLINE=1` with auto mode and fresh cache** → returns
    `AlreadyFresh` (env doesn't *force* offline if cache is already
    fresh; it just prevents fetching).
11. **Concurrency**: two threads calling `ensure_fresh(Auto)` on a stale
    cache with a mocked-slow fetch → only one fetch happens, both return
    fresh data. Use a counter atomic in the mock.

### Mocking `fetch_models`

`fetch_models` currently hits the network. For testable `ensure_fresh`,
extract a seam:

```rust
pub trait ModelFetcher {
    fn fetch(&self) -> Result<Vec<CachedModel>, MarsError>;
}

pub fn ensure_fresh_with<F: ModelFetcher>(
    mars_dir: &Path,
    ttl_hours: u32,
    mode: RefreshMode,
    fetcher: &F,
) -> Result<(ModelsCache, RefreshOutcome), MarsError>;

pub fn ensure_fresh(
    mars_dir: &Path,
    ttl_hours: u32,
    mode: RefreshMode,
) -> Result<(ModelsCache, RefreshOutcome), MarsError> {
    ensure_fresh_with(mars_dir, ttl_hours, mode, &HttpFetcher)
}
```

Tests use an in-memory fetcher; production uses `HttpFetcher` which
delegates to the existing `fetch_models` function. This keeps the real
call signature identical for callers while making the concurrency and
failure tests hermetic.

## Verification

- `cargo test --package mars-agents models::`
- `cargo clippy --all-targets -- -D warnings`
- Manual smoke: `rm -f .mars/models-cache.json && cargo run -- models
  list` in a test fixture should trigger a fetch via the test's stub path
  (covered by phase 3, but spot-check in an integration test if
  convenient).

## Guard Rails

- **Do not** bundle the phase 3/4 call-site rewires into this phase. The
  review of phase 2 must see only the helper in isolation.
- **Do not** rename `fetched_at` or change `ModelsCache`'s serialized
  shape. Unparseable tolerance is in `is_fresh`, not in the struct.
- If you hit a reason to change `ensure_fresh`'s signature, stop and
  surface it to the orchestrator — downstream phases rely on it.
