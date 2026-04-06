# Call Sites

Every consumer that reads the models cache either calls `ensure_fresh` or
(in the case of `mars models refresh`) uses the same lock primitive directly.
No consumer keeps its own freshness decision.

## 1. `mars sync` — `src/sync/mod.rs`

Context: around line 561, sync writes `.mars/models-merged.json` right after
building the new lock file. We want the models *catalog* (raw model IDs from
API) refreshed *before* the merged alias file is written, so that any
downstream reader seeing the new aliases also sees a catalog that covers
them.

Insertion point: immediately before the `match serde_json::to_string_pretty
(&dep_model_aliases)` block at line 559.

```rust
// Ensure the models catalog covers any new aliases we're about to persist.
let mode = resolve_refresh_mode(request.options.no_refresh_models);
let ttl = load_models_cache_ttl(ctx);
match crate::models::ensure_fresh(&ctx.project_root.join(".mars"), ttl, mode) {
    Ok((_, outcome)) => {
        report_refresh_outcome(&mut diag, outcome);
    }
    Err(err) => {
        diag.warn("models-cache-refresh", format!("{err}"));
        // Do not fail sync — sync's job is to land the alias config; the
        // catalog refresh is best-effort at sync time. Failure surfaces
        // loudly on the next `mars models list`/`resolve` call.
    }
}
```

Sync does **not** abort on `ensure_fresh` failure. Rationale: the user's
`sync` goal is to land manifest/alias changes. If the network is down, they
should still be able to sync, and the first actual agent spawn will surface
the cache problem in its own error path.

### New `SyncOptions` field

```rust
pub struct SyncOptions {
    pub force: bool,
    pub dry_run: bool,
    pub frozen: bool,
    pub no_refresh_models: bool,   // NEW
}
```

### New CLI flag in `cli/sync.rs`

```rust
pub struct SyncArgs {
    // ...existing fields...
    /// Skip the automatic models-cache refresh.
    #[arg(long)]
    pub no_refresh_models: bool,
}
```

Wired through the existing `SyncRequest` conversion.

## 2. `mars models list` — `src/cli/models.rs::run_list`

Replace:
```rust
let cache = models::read_cache(&mars)?;
// ...
if cache.fetched_at.is_none() {
    eprintln!("hint: no models cache — run `mars models refresh` for ...");
}
```

With:
```rust
let mode = resolve_refresh_mode(args.no_refresh_models);
let ttl = load_models_cache_ttl(ctx);
let (cache, outcome) = models::ensure_fresh(&mars, ttl, mode)?;
warn_on_stale_fallback(&outcome);
```

Add `--no-refresh-models: bool` to `ListArgs`.

`mars models list` *does* propagate `ensure_fresh`'s errors (unlike sync) —
if the cache is empty and offline, listing aliases is the command's entire
job, so failing loudly is correct.

## 3. `mars models resolve` — `src/cli/models.rs::run_resolve`

Same pattern as `list`. Add `--no-refresh-models` to `ResolveAliasArgs`.
Resolve fails loudly if the cache is empty and offline.

`meridian`'s agent-launch path shells out to this command, so threading
`ensure_fresh(Auto)` into `run_resolve` is what gives meridian the refresh
guarantee "for free".

## 4. `mars models refresh` — `src/cli/models.rs::run_refresh`

Continues to exist as the explicit online entry point. Does **not** route
through `ensure_fresh`:

```rust
fn run_refresh(ctx: &MarsContext, json: bool) -> Result<i32, MarsError> {
    let mars = mars_dir(ctx);
    let _guard = crate::fs::FileLock::acquire(&mars.join(".models-cache.lock"))?;
    eprint!("Fetching models catalog... ");
    let fetched = models::fetch_models()?;
    let count = fetched.len();
    let cache = ModelsCache {
        models: fetched,
        fetched_at: Some(now_unix_secs()),
    };
    models::write_cache(&mars, &cache)?;
    // ...existing output...
}
```

Why bypass `ensure_fresh`? Because:

1. `mars models refresh` always fetches, regardless of `MARS_OFFLINE`. The
   user typed it explicitly.
2. `ensure_fresh` intentionally coerces `MARS_OFFLINE → Offline`. Routing
   `refresh` through it would require a special-case escape hatch, which
   complicates the helper for one caller.
3. Sharing the lock primitive (not the function) is enough to stay
   concurrent-safe with the other call sites.

This is the single "doesn't use `ensure_fresh`" exception and it's worth it.

## 5. `meridian` agent-launch

No direct change on the mars side; meridian already calls
`mars models resolve --json`, which now runs `ensure_fresh(Auto)` internally.
See `meridian-integration.md` for the small timeout adjustment needed on
meridian's subprocess call.

## Shared Helpers

Two small helpers live in `cli/models.rs` (or a new `cli/models_support.rs`)
to avoid duplication across call sites:

```rust
/// Resolve the refresh mode from CLI flag + env.
pub fn resolve_refresh_mode(no_refresh_flag: bool) -> RefreshMode {
    if no_refresh_flag || std::env::var_os("MARS_OFFLINE").is_some() {
        RefreshMode::Offline
    } else {
        RefreshMode::Auto
    }
}

/// Load configured TTL; default 24.
pub fn load_models_cache_ttl(ctx: &MarsContext) -> u32 {
    crate::config::load(&ctx.project_root)
        .map(|c| c.settings.models_cache_ttl_hours)
        .unwrap_or(24)
}

/// Surface a stale-fallback warning to stderr (non-JSON output only).
pub fn warn_on_stale_fallback(outcome: &RefreshOutcome) { /* ... */ }
```

`sync` also uses these — they live in a module both `cli/` and `sync/` can
see. Simplest placement: add to `src/models/mod.rs` next to `ensure_fresh`.

## Error Messages

When `ensure_fresh` errors with `ModelCacheUnavailable`, callers print:

```
error: models cache is empty and no refresh is allowed (<reason>).
       Run `mars models refresh` to populate it, or unset MARS_OFFLINE.
```

JSON callers return the same message under an `"error"` key and exit code
1, consistent with mars's existing JSON error shape.
