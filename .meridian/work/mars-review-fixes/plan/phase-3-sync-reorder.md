# Phase 3: Sync Pipeline Reorder (F12)

## Scope

Move the config save in `src/sync/mod.rs` from before apply (step 15) to after lock write (step 17→18), making crash during apply recoverable by re-running the same command.

## Files to Modify

### `src/sync/mod.rs` — `execute()`

Move the config save block (currently between steps 15-16) to after the lock write (after step 17):

**Current order (lines ~208-234):**
```
Step 15: save config/local (if mutation + not dry_run)
Step 16: apply::execute
Step 17: lock::write
```

**New order:**
```
Step 16: apply::execute
Step 17: lock::write
Step 18: save config/local (if mutation + not dry_run)
```

The code block to move is:
```rust
// This block moves from before apply to after lock write:
if has_mutation && !request.options.dry_run {
    match request.mutation {
        Some(ConfigMutation::SetOverride { .. } | ConfigMutation::ClearOverride { .. }) => {
            crate::config::save_local(root, &local)?;
        }
        Some(
            ConfigMutation::UpsertSource { .. }
            | ConfigMutation::RemoveSource { .. }
            | ConfigMutation::SetRename { .. }
            | ConfigMutation::SetLink { .. }
            | ConfigMutation::ClearLink { .. },
        ) => {
            crate::config::save(root, &config)?;
        }
        None => {}
    }
}
```

**Important: the `request.mutation` match needs to handle the borrow correctly.** The `request` is consumed partially by the time we reach the new position. Check that `request.mutation` is still accessible — it may need to be moved to a local variable before the apply call.

Actually, looking at the code: `request.mutation` is a field on `&SyncRequest`. The `apply::execute` takes `&sync_plan` and `&request.options`, not consuming `request`. So `request.mutation` is still accessible after apply. No ownership issue.

## Dependencies

- Independent of Phase 1 and Phase 2
- Can run in parallel with them

## Verification Criteria

- [ ] `cargo test` passes
- [ ] `cargo clippy --all-targets --all-features` clean
- [ ] Existing `lock_written_after_apply` test still passes
- [ ] `mars add` followed by `mars sync` still works (the mutation is still applied, just saved later)
- [ ] Verify: config file is updated after a successful `mars add <source>` (not before apply)
