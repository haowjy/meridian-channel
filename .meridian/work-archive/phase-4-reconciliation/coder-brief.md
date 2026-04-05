# Phase 4 Coder Brief: Shared Reconciliation Layer

**Codebase:** `/home/jimyao/gitrepos/mars-agents/`
**Task:** Extract shared filesystem operations into a new `reconcile` module with two layers.

## What to Build

### 1. Create `src/reconcile/fs_ops.rs` (Layer 1 — Atomic FS Primitives)

Extract and create these functions:

```rust
/// Atomic file write via tmp+rename in the same directory.
pub fn atomic_write_file(dest: &Path, content: &[u8]) -> Result<(), MarsError>;
```
This is a **thin wrapper** around the existing `crate::fs::atomic_write()`. Just delegate to it.

```rust
/// Atomic directory install: copy tree to tmp dir in same parent, then rename.
pub fn atomic_install_dir(source: &Path, dest: &Path) -> Result<(), MarsError>;
```
Thin wrapper around `crate::fs::atomic_install_dir()`.

```rust
/// Atomic file copy: read source (following symlinks), write to tmp, rename to dest.
/// NEW — doesn't exist yet. Reads the source file content, then uses atomic_write_file to write to dest.
pub fn atomic_copy_file(source: &Path, dest: &Path) -> Result<(), MarsError>;
```

```rust
/// Atomic directory copy: deep copy source tree (following symlinks) to tmp, rename to dest.
/// NEW — doesn't exist yet. Reads source following symlinks, writes copy atomically.
/// Uses the same tmp+rename pattern as atomic_install_dir.
pub fn atomic_copy_dir(source: &Path, dest: &Path) -> Result<(), MarsError>;
```

```rust
/// Create a symlink atomically (remove existing + create).
pub fn atomic_symlink(link_path: &Path, target: &Path) -> Result<(), MarsError>;
```
Extract from `sync/apply.rs` `PlannedAction::Symlink` handler (lines 228-254) — the remove-existing + create pattern.

```rust
/// Remove a file or directory tree safely.
pub fn safe_remove(path: &Path) -> Result<(), MarsError>;
```
Remove whatever exists at path — handles files, dirs, and symlinks. Use `symlink_metadata` to check, then appropriate removal.

```rust
/// Compute hash of file or directory for comparison.
pub fn content_hash(path: &Path, kind: ItemKind) -> Result<ContentHash, MarsError>;
```
Thin wrapper around `crate::hash::compute_hash()`, returning `ContentHash`.

### 2. Create `src/reconcile/mod.rs` (Layer 2 — Item-Level Reconciliation)

```rust
pub mod fs_ops;

// Re-export layer 1
pub use fs_ops::*;
```

Define the Layer 2 types and functions:

```rust
pub enum DestinationState {
    Empty,
    File { hash: ContentHash },
    Directory { hash: ContentHash },
    Symlink { target: PathBuf },
}

pub enum DesiredState {
    CopyFile { source: PathBuf, hash: ContentHash },
    CopyDir { source: PathBuf, hash: ContentHash },
    Symlink { target: PathBuf },
    Absent,
}

pub enum ReconcileOutcome {
    Created,
    Updated,
    Removed,
    Skipped { reason: &'static str },
    Conflict { existing: DestinationState, desired: DesiredState },
}

/// Scan a destination to determine its current state.
pub fn scan_destination(path: &Path) -> DestinationState;

/// Reconcile a single destination path to desired state.
pub fn reconcile_one(dest: &Path, desired: DesiredState, force: bool) -> Result<ReconcileOutcome, MarsError>;
```

`scan_destination`: Use `symlink_metadata` → if not found, `Empty`. If symlink, `Symlink`. If file, compute hash, `File`. If dir, compute hash, `Directory`.

`reconcile_one`: Match on desired state:
- `Absent`: if destination exists, `safe_remove` → `Removed`. If empty, `Skipped`.
- `CopyFile`: scan dest. If empty → `atomic_copy_file` → `Created`. If file with same hash → `Skipped`. If file with diff hash and !force → `Conflict`. If force or symlink → `safe_remove` + `atomic_copy_file` → `Updated`.
- `CopyDir`: same logic but with `atomic_copy_dir`.
- `Symlink`: if dest is already correct symlink → `Skipped`. Otherwise remove + `atomic_symlink` → `Created`/`Updated`.

### 3. Modify `src/lib.rs`

Add `pub mod reconcile;` to the module list.

### 4. Modify `src/sync/apply.rs`

Replace inline atomic operations with calls to `reconcile::fs_ops::*`:

- In `install_item()` (line 363-383): Replace `crate::fs::atomic_write` → `crate::reconcile::fs_ops::atomic_write_file`. Replace `crate::fs::atomic_install_dir` → `crate::reconcile::fs_ops::atomic_install_dir`. Replace `crate::fs::atomic_install_dir_filtered` — keep using `crate::fs::atomic_install_dir_filtered` since the filtered variant is apply-specific (used only for flat skills).
- In the `Merge` handler (line 150): Replace `crate::fs::atomic_write` → `crate::reconcile::fs_ops::atomic_write_file`.
- In `cache_base_content()` (line 425-455): Replace `crate::fs::atomic_write` → `crate::reconcile::fs_ops::atomic_write_file`.
- In `PlannedAction::Symlink` handler (lines 222-272): Replace the inline remove-existing + create-symlink logic with `crate::reconcile::fs_ops::atomic_symlink`. Keep the relative symlink path computation as-is (that's apply-specific). The cleanup of existing content before creating the symlink should use the atomic_symlink function.
- In `PlannedAction::Remove` handler (line 174-193): Replace `crate::fs::remove_item` → `crate::reconcile::fs_ops::safe_remove`.

### 5. Modify `src/link.rs`

- `hash_file()` (line 156-160): Replace with `crate::reconcile::fs_ops::content_hash` or keep the simple inline hash (it's just for comparison, not the full content_hash API). Actually, keep `hash_file` as-is — it returns `Option<String>` which is different from the reconcile API. The link module's hash_file is a simplified version for conflict detection.
- `merge_and_link()` (line 163-192): The `std::fs::copy` + `std::fs::remove_file` pattern for moving files is link-specific (cross-fs safe move). Keep it. But replace `create_symlink()` usage — actually the `create_symlink` function in link.rs IS the symlink creation. Replace it with a thin call to `crate::reconcile::fs_ops::atomic_symlink` (but note: `atomic_symlink` handles removing existing, while `create_symlink` doesn't — and in `merge_and_link`, the dir is already cleaned up before calling `create_symlink`, so this is fine).
- Actually, let me reconsider link.rs: The main shared operations are `create_symlink` and the hash comparison. Replace `create_symlink` with `reconcile::fs_ops::atomic_symlink`. But `atomic_symlink` removes existing first, while in link.rs the path is already cleaned up. That's fine — `atomic_symlink` checks with `symlink_metadata` first, so it's a no-op if nothing exists.

**Key constraint: `create_symlink` in link.rs uses `link_target` (relative path), while `atomic_symlink` in reconcile should also work with relative targets.** Make sure `atomic_symlink` accepts any `&Path` as target (not just absolute).

## Important Constraints

- **Pure refactor.** No behavioral change. `mars sync` and `mars link` output must be identical.
- **Atomicity guarantees preserved.** Every write path must remain tmp+rename.
- **`atomic_copy_file` and `atomic_copy_dir` are NEW** — they don't exist yet. They follow symlinks (reads through the symlink, writes a real copy).
- **Unit tests required** for `atomic_copy_file` and `atomic_copy_dir`, especially the symlink-following behavior.
- Keep `crate::fs` module for lock-only operations (FileLock) and the filtered install variant.

## Verification

```bash
cd /home/jimyao/gitrepos/mars-agents
cargo build
cargo test
cargo clippy
```

All must pass with no new warnings.
