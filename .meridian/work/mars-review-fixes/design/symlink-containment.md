# F1 + F3: Symlink Containment

## F1: Managed Root Escape via Symlink

### Problem

`MarsContext::new` canonicalizes `managed_root`, then derives `project_root = managed_root.parent()`. If `.agents/` is a symlink to `/tmp/evil/agents/`, canonicalization resolves it to `/tmp/evil/agents/`, and `project_root` becomes `/tmp/evil/`. All operations then target the wrong project.

Similarly, `--root /tmp/evil/agents` lets a user (or script) point mars at an arbitrary directory, making `project_root = /tmp/evil/`.

### Analysis

The `project_root` is used for:
1. Link target resolution (`ctx.project_root.join(&target_name)`) — creates symlinks relative to the derived project root
2. Local path source resolution — resolves relative source paths against project root

Both are dangerous if project_root escapes the real project.

### Design: Containment Check

Add a post-canonicalize validation in `MarsContext::new`:

```rust
impl MarsContext {
    pub fn new(managed_root: PathBuf) -> Result<Self, MarsError> {
        let canonical = if managed_root.exists() {
            managed_root.canonicalize().unwrap_or(managed_root.clone())
        } else {
            managed_root.clone()
        };

        let project_root = canonical.parent()
            .ok_or_else(|| /* existing error */)?
            .to_path_buf();

        // NEW: If managed_root was provided as a relative path rooted in cwd,
        // verify the canonical project_root still contains the original location.
        // This catches symlinks that redirect .agents/ outside the project.
        if managed_root.exists() && canonical != managed_root {
            // The original (pre-canonicalize) parent is the "expected" project root
            let original_parent = if managed_root.is_absolute() {
                managed_root.parent().map(|p| p.to_path_buf())
            } else {
                std::env::current_dir().ok()
                    .and_then(|cwd| cwd.join(&managed_root).parent().map(|p| p.to_path_buf()))
            };

            if let Some(expected) = original_parent {
                let expected_canon = expected.canonicalize().unwrap_or(expected);
                if !canonical.starts_with(&expected_canon) {
                    return Err(MarsError::Config(ConfigError::Invalid {
                        message: format!(
                            "managed root {} resolves to {} which is outside the project at {}. \
                             The managed root may be a symlink pointing outside the project.",
                            managed_root.display(),
                            canonical.display(),
                            expected_canon.display(),
                        ),
                    }));
                }
            }
        }

        Ok(MarsContext { managed_root: canonical, project_root })
    }
}
```

**Why this approach over alternatives:**

- **Alternative: never canonicalize** — breaks symlink detection in link.rs (relative vs absolute path comparison fails)
- **Alternative: canonicalize but don't use parent** — requires threading the original project root separately, touching every call site
- **This approach**: validates at the boundary (MarsContext construction), fails fast, zero impact on downstream code

**Edge case: `--root` flag**

When the user passes `--root /some/path`, there's no "original parent" to compare against — the user explicitly chose that root. We skip the containment check for explicit `--root` since the user is intentionally pointing mars at that location. The check only applies to auto-discovered roots.

To implement this, `MarsContext::new` gets an additional parameter or the check is done in `find_agents_root` before calling `MarsContext::new`:

```rust
pub fn find_agents_root(explicit: Option<&Path>) -> Result<MarsContext, MarsError> {
    if let Some(root) = explicit {
        // User explicitly chose this root — trust it
        return MarsContext::new(root.to_path_buf());
    }

    // Auto-discovered root — validate containment
    let cwd = std::env::current_dir()?;
    // ... walk up ...
    let ctx = MarsContext::new(candidate)?;
    // Validate canonical managed_root is under cwd's tree
    let cwd_canon = cwd.canonicalize().unwrap_or(cwd);
    if !ctx.managed_root.starts_with(&cwd_canon)
        && !cwd_canon.starts_with(&ctx.project_root)
    {
        return Err(MarsError::Config(ConfigError::Invalid {
            message: format!(
                "auto-discovered managed root {} resolves outside the project tree. \
                 This may indicate a symlink pointing outside the project. \
                 Use --root to override if intentional.",
                ctx.managed_root.display(),
            ),
        }));
    }
    Ok(ctx)
}
```

This approach:
- Catches symlinked `.agents/` during auto-discovery
- Allows explicit `--root` for intentional cross-project operations
- Validates at the boundary before any mutations happen

## F3: Symlink Following in check/doctor Scanning

### Problem

Both `check.rs` and `doctor.rs` scan `agents/` and `skills/` directories, reading files and parsing frontmatter. If a skill directory is a symlink to `/etc/` or a huge external tree, the scan follows it without bounds.

### Design: Symlink-Aware Scanning

**Policy: skip symlinked entries and warn.**

Rationale:
- Mars owns the `agents/` and `skills/` directories — everything in them should be regular files/dirs installed by mars or created by the user
- Symlinks inside managed directories are not part of the mars installation model
- Following symlinks opens unbounded I/O (both for read time and for path escape)
- Skipping with a warning is safe — if the user intentionally symlinked something, the warning tells them mars can't validate it

**Implementation:**

Add a helper that both check.rs and doctor.rs use when iterating entries:

```rust
// In a shared location (e.g., src/discover/mod.rs or a new src/scan.rs)
/// Check if a path is a symlink. Returns true if it is.
pub fn is_symlink(path: &Path) -> bool {
    path.symlink_metadata()
        .map(|m| m.file_type().is_symlink())
        .unwrap_or(false)
}
```

In scanning loops, before processing each entry:

```rust
// In check.rs agent scanning:
for entry in entries {
    let path = entry.path();
    if is_symlink(&path) {
        warnings.push(format!(
            "skipping symlinked agent `{}` — mars cannot validate symlinked entries",
            path.display()
        ));
        continue;
    }
    // ... existing processing ...
}

// Same pattern for skill scanning in check.rs and doctor.rs
```

**What about `walkdir` in link.rs?**

`link.rs` uses `walkdir::WalkDir` which follows symlinks by default. This is in the merge-scan path where we're comparing target dir contents against managed root. Here, following symlinks is less dangerous because:
1. The target dir is user-provided (e.g., `.claude/`)
2. We're only reading for hash comparison, not executing
3. The scan is bounded to the target dir structure

However, for defense in depth, add `.follow_links(false)` to the walkdir calls in `scan_dir_recursive` and skip symlink entries:

```rust
for entry in walkdir::WalkDir::new(target_subdir)
    .follow_links(false)  // NEW
    .into_iter()
    .filter_map(|e| e.ok())
{
    if entry.file_type().is_symlink() {
        // Treat symlinks in target dirs as conflicts (not transparent)
        conflicts.push(ConflictInfo { ... });
        continue;
    }
    // ... existing logic ...
}
```

## Files to Modify

- `src/cli/mod.rs` — containment check in `find_agents_root()`, ~15 lines
- `src/cli/check.rs` — symlink skip+warn in agent and skill scanning, ~10 lines
- `src/cli/doctor.rs` — symlink skip+warn in agent and skill scanning, ~10 lines
- `src/cli/link.rs` — `.follow_links(false)` and symlink handling in `scan_dir_recursive`, ~8 lines

## Verification

- `cargo test` passes
- Create a symlinked `.agents/` pointing outside the project → `mars sync` errors with clear message
- Create a symlinked skill dir → `mars check` and `mars doctor` skip it with warning
- Normal (non-symlinked) operation is unchanged
