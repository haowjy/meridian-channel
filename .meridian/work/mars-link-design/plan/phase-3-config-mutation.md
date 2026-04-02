# Phase 3: ConfigMutation Extension & mutate_config

**Design refs**: [config-mutations.md](../design/config-mutations.md)

## Scope

Add `SetLink`/`ClearLink` variants to `ConfigMutation` and add `sync::mutate_config()` — a lightweight config mutation path that acquires sync.lock without running the full sync pipeline. This eliminates the lock bypass in link.rs.

## Files to Modify

- `src/sync/mod.rs` — Add `ConfigMutation::SetLink`/`ClearLink`, add `mutate_config()` fn, update `apply_mutation()` and `persist` match arms
- `src/cli/link.rs` — Remove `persist_link()` and `remove_link()` functions (replaced by `sync::mutate_config`)

## Interface Contract

```rust
// src/sync/mod.rs

pub enum ConfigMutation {
    // ... existing variants ...
    /// Add a link target to settings.links (idempotent).
    SetLink { target: String },
    /// Remove a link target from settings.links.
    ClearLink { target: String },
}

/// Apply a config mutation under sync lock, without running the full sync pipeline.
/// Used for settings changes (links) that don't require resolution/installation.
pub fn mutate_config(root: &Path, mutation: &ConfigMutation) -> Result<(), MarsError> {
    let lock_path = root.join(".mars").join("sync.lock");
    let _sync_lock = crate::fs::FileLock::acquire(&lock_path)?;

    let mut config = crate::config::load(root)?;
    apply_mutation(&mut config, mutation)?;
    crate::config::save(root, &config)?;

    Ok(())
}
```

## Changes

### sync/mod.rs

1. Add two variants to `ConfigMutation`:
   ```rust
   SetLink { target: String },
   ClearLink { target: String },
   ```

2. Add arms to `apply_mutation`:
   ```rust
   ConfigMutation::SetLink { target } => {
       if !config.settings.links.contains(target) {
           config.settings.links.push(target.clone());
       }
       Ok(())
   }
   ConfigMutation::ClearLink { target } => {
       config.settings.links.retain(|l| l != target);
       Ok(())
   }
   ```

3. Add arm to the persist match in `execute()` (step 15):
   ```rust
   Some(ConfigMutation::SetLink { .. } | ConfigMutation::ClearLink { .. }) => {
       crate::config::save(root, &config)?;
   }
   ```

4. Add public `mutate_config()` function (see interface contract above).

### cli/link.rs

1. Delete `persist_link()` function (lines 160-167)
2. Delete `remove_link()` function (lines 170-174)
3. Update `run()` to call `sync::mutate_config()` instead of `persist_link()`
4. Update `unlink()` to call `sync::mutate_config()` instead of `remove_link()`

```rust
// In run(), after creating symlinks:
crate::sync::mutate_config(
    &ctx.managed_root,
    &ConfigMutation::SetLink { target: args.target.clone() },
)?;

// In unlink(), after removing symlinks:
crate::sync::mutate_config(
    &ctx.managed_root,
    &ConfigMutation::ClearLink { target: target_name.to_string() },
)?;
```

## Dependencies

- **Requires**: Phase 1 (error model), Phase 2 (MarsContext — link.rs uses `ctx.managed_root`)
- **Produces**: `sync::mutate_config()` function, `ConfigMutation::SetLink/ClearLink`
- **Independent of**: Phases 4, 5

## Verification Criteria

- [ ] `cargo build` succeeds
- [ ] `cargo test` passes
- [ ] New test: `mutate_config` with `SetLink` adds to settings.links under lock
- [ ] New test: `mutate_config` with `SetLink` is idempotent (adding twice = one entry)
- [ ] New test: `mutate_config` with `ClearLink` removes from settings.links
- [ ] New test: `apply_mutation` handles SetLink/ClearLink correctly
- [ ] `persist_link` and `remove_link` functions no longer exist in link.rs

## Patterns to Follow

Look at how `add.rs` constructs a `SyncRequest` with a `ConfigMutation` — that's the established pattern for config mutations. The `mutate_config` function is the lightweight equivalent for mutations that don't need the full pipeline.
