# Phase 4: Wire `mars sync`

**Repo:** mars-agents
**Depends on:** Phase 2
**Parallel with:** Phase 3
**Est. size:** ~60 LoC + tests

## Goal

Call `ensure_fresh(Auto)` inside `mars sync` so that new aliases landing in
`models-merged.json` are always accompanied by a catalog that covers them.
Sync never aborts on cache refresh failure — it warns and continues.

## Files

- `src/cli/sync.rs`
  - Add `--no-refresh-models: bool` to `SyncArgs`.
  - Thread the flag into `SyncOptions.no_refresh_models`.
- `src/sync/mod.rs`
  - Add `no_refresh_models: bool` to `SyncOptions`.
  - Call `ensure_fresh` right before the `models-merged.json` write block
    (~line 559 in current file).
  - Report `RefreshOutcome` via the existing `DiagnosticCollector` warn
    channel on `StaleFallback` or errors; silent on `AlreadyFresh` and
    `Refreshed`.

## Implementation

### Insertion point (`sync/mod.rs` around line 559)

```rust
// Catalog refresh: ensure the models cache covers any new aliases we're
// about to persist. Best-effort — warn and continue on failure so sync
// never blocks on network hiccups.
if !request.options.dry_run {
    let mars_path = ctx.project_root.join(".mars");
    let ttl = crate::models::load_models_cache_ttl(ctx);
    let mode = crate::models::resolve_refresh_mode(
        request.options.no_refresh_models,
    );
    match crate::models::ensure_fresh(&mars_path, ttl, mode) {
        Ok((_, crate::models::RefreshOutcome::StaleFallback { reason })) => {
            diag.warn(
                "models-cache-refresh",
                format!("using stale models cache: {reason}"),
            );
        }
        Ok((_, crate::models::RefreshOutcome::Offline)) => {
            // Offline and cache present — silent. Consumers that need the
            // catalog will surface their own errors.
        }
        Ok(_) => { /* AlreadyFresh or Refreshed — silent */ }
        Err(err) => {
            diag.warn(
                "models-cache-refresh",
                format!("failed to refresh models cache: {err}"),
            );
        }
    }
}
```

This block goes *before* the existing `match serde_json::to_string_pretty
(&dep_model_aliases)` so the catalog is populated first, even though the
two files are logically independent. Ordering aids debuggability: a user
looking at "did sync finish?" sees catalog, then merged, then done.

### `SyncOptions`

```rust
pub struct SyncOptions {
    pub force: bool,
    pub dry_run: bool,
    pub frozen: bool,
    pub no_refresh_models: bool,  // NEW
}
```

All existing `SyncOptions { ... }` literals must be updated. Search for
construction sites: `cli/sync.rs`, tests, any mutation flow.

### `SyncArgs`

```rust
/// Skip the automatic models-cache refresh during sync.
#[arg(long)]
pub no_refresh_models: bool,
```

Wire into `SyncRequest::options` in `cli/sync.rs::run`.

## Verification

- `cargo test --package mars-agents sync::`
- Smoke:
  1. `rm -f .mars/models-cache.json`
  2. `cargo run -- sync --force` in a test fixture → cache populated after
     sync.
  3. `MARS_OFFLINE=1 cargo run -- sync --force` → cache remains empty,
     sync still exits 0.
  4. `cargo run -- sync --force --no-refresh-models` → same as case 3.

## Unit Tests

- `SyncArgs` parser test for `--no-refresh-models`.
- A `SyncOptions` construction test ensuring the field defaults to
  `false` in the obvious constructor path.
- An integration-style test for the sync pipeline that sets a test
  fetcher (if the phase-2 `ensure_fresh_with` seam is used, point sync
  at a test context). Otherwise rely on phase-5 smoke tests.

## Guard Rails

- **Do not** make sync fail on ensure_fresh errors. The requirements are
  explicit that sync should complete even offline.
- **Do not** call `ensure_fresh` inside `dry_run` — dry-run is
  side-effect-free by convention, and refreshing the cache is a
  side-effect.
- **Do not** move the `models-merged.json` write into `ensure_fresh` or
  vice versa — they stay separate concerns.
