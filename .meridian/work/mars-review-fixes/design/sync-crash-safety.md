# F12 + F13: Sync Crash Safety

## F12: Sync Pipeline Not Retry-Safe

### Problem

The sync pipeline in `src/sync/mod.rs` saves config at step 15 (before apply) and lock at step 17 (after apply). If mars crashes during step 16 (apply), the state is:

- **Config**: updated (new source added/removed)
- **Lock**: stale (still reflects old state)
- **Disk**: partially installed (some files from the new source, not all)

On the next `mars sync`, the resolver reads the updated config and builds a target state. The stale lock says the old items exist. The diff between them may not correctly identify the partially-installed files, leading to:
- Unmanaged file collision errors (new files on disk not in lock)
- Missing file reports (lock says files exist but apply was interrupted)

### Current Pipeline Order

```
Step 15: Save config (if mutation)       ← crash here = config updated, disk/lock stale
Step 16: Apply plan (install/remove)     ← crash here = disk partial, lock stale
Step 17: Write lock                      ← only reached on success
```

### Design: Save Config and Lock Together After Apply

Reorder so config, lock, and disk are consistent at every crash point:

```
Step 15: (removed — config NOT saved yet)
Step 16: Apply plan (install/remove)
Step 17: Write lock
Step 18: Save config (if mutation)       ← NEW position
```

**Crash analysis:**

| Crash point | Config | Lock | Disk | Recovery |
|---|---|---|---|---|
| During apply (step 16) | old | old | partial | Next `sync` re-runs same mutation → converges |
| After lock, before config (step 17-18) | old | new | new | Next `sync` reads old config + new lock. If mutation was `add`, the lock has the new source but config doesn't — `mars sync` re-adds it. If `remove`, lock lacks it, config still has it — `mars sync` removes again. Both converge. |
| After config (step 18) | new | new | new | Clean |

**Wait — is "old config + new lock" safe?**

Yes, because the sync pipeline's first step is "apply mutation to config." If config still has the old state, the mutation replays:
- **Add source X**: Config already lacks X (old), mutation adds it, resolver resolves, diff finds items already on disk (from the successful apply), diff is empty or skip-only, lock is re-written identically. Converges.
- **Remove source X**: Config still has X (old), mutation removes it, resolver builds state without X, diff finds X's items on disk and in lock, plans removal, applies, writes new lock. Converges.

**Alternative considered: journaled approach (write intent file, apply, commit).**

This is more complex and unnecessary. The key insight is that the sync pipeline is already idempotent — re-running it with the same mutation converges to the same state. The only thing that breaks idempotency is saving config early (making the mutation disappear before apply completes). Moving config save to after apply restores idempotency.

### Implementation

In `src/sync/mod.rs`, move the config save block (currently step 15) to after the lock write (currently step 17):

```rust
// Step 16: Apply plan.
let applied = apply::execute(root, &sync_plan, &request.options, &cache_bases_dir)?;

// Step 17: Write lock file.
if !request.options.dry_run {
    let new_lock = crate::lock::build(&graph, &applied, &old_lock)?;
    crate::lock::write(root, &new_lock)?;
}

// Step 18: Persist config mutation (after apply+lock so crash leaves old config).
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

## F13: atomic_install_dir Gap

### Problem

In `src/fs/mod.rs`, `atomic_install_dir` does:

```rust
if dest.exists() {
    fs::remove_dir_all(dest)?;   // ← dest gone
}
// crash here = dest missing entirely
fs::rename(&tmp_path, dest)?;    // ← dest restored
```

If mars crashes between the remove and the rename, the installed skill directory is simply gone. The next `mars sync` would need to reinstall it.

### Design: Rename-Old-Then-Rename-New

```rust
pub fn atomic_install_dir(src: &Path, dest: &Path) -> Result<(), MarsError> {
    let parent = dest.parent().unwrap_or(Path::new("."));
    fs::create_dir_all(parent)?;

    let tmp_dir = tempfile::TempDir::new_in(parent)?;
    copy_dir_recursive(src, tmp_dir.path())?;
    let tmp_path = tmp_dir.keep();

    if dest.exists() {
        // Rename old to .old (atomic — old is still accessible)
        let old_path = dest.with_extension("old");
        // Clean up any stale .old from a prior crash
        if old_path.exists() {
            fs::remove_dir_all(&old_path)?;
        }
        fs::rename(dest, &old_path)?;
        // Rename new into place (atomic)
        if let Err(e) = fs::rename(&tmp_path, dest) {
            // Rollback: restore old
            let _ = fs::rename(&old_path, dest);
            let _ = fs::remove_dir_all(&tmp_path);
            return Err(e.into());
        }
        // Clean up old
        let _ = fs::remove_dir_all(&old_path);
    } else {
        fs::rename(&tmp_path, dest)?;
    }

    Ok(())
}
```

**Crash analysis:**

| Crash point | State | Recovery |
|---|---|---|
| Before rename-to-old | `dest` intact, `tmp` exists | `tmp` is orphaned in parent dir, cleaned up by OS temp cleanup or next install |
| After rename-to-old, before rename-new | `dest.old` exists, `dest` gone, `tmp` exists | Next `mars sync` detects missing dest, reinstalls. `dest.old` is stale but harmless. Startup cleanup (optional) can detect and restore `.old` files. |
| After rename-new, before cleanup | `dest` new, `dest.old` stale | `.old` is cleaned up on next install of the same dest, or by the cleanup at the start of the function. |

The gap between rename-to-old and rename-new still exists but is much smaller (two renames vs. a recursive delete + rename), and recovery is straightforward — the `.old` sentinel makes the state diagnosable.

**Startup cleanup (optional enhancement):**

Add a check at the top of `atomic_install_dir` (already shown above — the `if old_path.exists()` cleanup). This handles stale `.old` dirs from prior crashes.

## Files to Modify

- `src/sync/mod.rs` — reorder steps 15-17 to 16-17-18, ~20 lines moved
- `src/fs/mod.rs` — rewrite `atomic_install_dir` with rename-old pattern, ~25 lines

## Verification

- `cargo test` passes (including existing `atomic_install_dir` tests)
- `lock_written_after_apply` test still passes
- Add test: verify `.old` cleanup when stale `.old` exists
- Add test: verify dest is never missing (old renamed before new placed)
