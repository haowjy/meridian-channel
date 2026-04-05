# Phase 4 Decision Log

## D1: atomic_symlink uses tmp-symlink + rename pattern

**What:** Changed `atomic_symlink` from remove+create to tmp-symlink+rename.

**Why:** Reviewer (opus) identified that remove-then-create leaves a gap where the path doesn't exist, violating the atomicity guarantee. `rename(2)` atomically replaces non-directory entries.

**Alternatives rejected:** Keeping remove+create — acceptable under flock but Phase 7 callers may not hold the sync lock.

## D2: reconcile_one Symlink arm respects force flag

**What:** Added force check to the Symlink arm catch-all in `reconcile_one`, matching CopyFile/CopyDir behavior.

**Why:** Without this, a user's real file/directory at the destination would be silently deleted when reconciling to Symlink state without force=true.

## D3: copy_dir_following_symlinks uses plain fs::write inside temp dir

**What:** Changed per-file copies inside the temp directory from `atomic_copy_file` (tmp+rename) to plain `fs::read`+`fs::write`.

**Why:** Files are being written into a temp directory that hasn't been placed at the final destination yet. The atomicity comes from the final `rename` of the enclosing temp dir, not per-file atomics. Also added broken symlink detection with descriptive error.

## D4: link.rs merge_and_link keeps raw fs::copy for cross-fs moves

**What:** Did NOT replace `std::fs::copy` + `std::fs::remove_file` in `merge_and_link` with reconcile ops.

**Why:** The spec explicitly says "Link-specific: the merge-unique-files-then-adopt algorithm." This is a cross-filesystem move operation (copy+delete), not an install. It's part of link's unique algorithm that adopts an existing target directory. The atomicity model is different — individual files are being migrated, not atomically installed.

**Reviewer disagreement:** R2 flagged this as High. I disagree because the spec's "what's shared vs. module-specific" section explicitly lists this algorithm as link-specific.

## D5: Layer 2 (reconcile_one, scan_destination) is scaffolding for Phase 7

**What:** Layer 2 has no callers in the current codebase.

**Why:** The spec says Layer 2 is used by "content apply" and "target sync." Target sync doesn't exist yet (Phase 7). apply.rs has merge/base-caching/checksum logic that doesn't map to reconcile_one's simpler model. Phase 7 will be the first real consumer. Creating the types now means Phase 7 imports clean primitives instead of duplicating logic.

**Reviewer disagreement:** R2 flagged as Medium (dead code). This is intentional scaffolding per the design spec.

## D6: atomic_install_dir_filtered stays in crate::fs

**What:** The filtered variant of atomic_install_dir is still accessed directly from `crate::fs`, not reconcile.

**Why:** The filtered variant is apply-specific (used only for flat skill repos). The phase spec says "keep fs/mod.rs for lock-only operations and have reconcile import from it — decide based on what's cleaner." The filtered variant with `excluded_top_level` is an apply-specific concern, not a shared primitive.

## D7: scan_destination_checked hardcodes ItemKind mapping

**What:** Files hashed as Agent, directories hashed as Skill in scan_destination.

**Why:** This matches the current codebase convention. Callers (Phase 7's target sync) must compute desired hashes with the same convention. If Phase 7 needs different hashing, scan_destination can be parameterized then. Premature abstraction now would add complexity without a concrete consumer.
