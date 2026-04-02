# Phase 4: Symlink Containment (F1, F3)

## Scope

1. Add containment validation in `find_agents_root` for auto-discovered roots
2. Add symlink-aware scanning in check.rs, doctor.rs, and link.rs

## Files to Modify

### `src/cli/mod.rs` — `find_agents_root()`

After auto-discovering a candidate root and building `MarsContext`, validate that the canonical managed_root is within the project tree:

```rust
pub fn find_agents_root(explicit: Option<&Path>) -> Result<MarsContext, MarsError> {
    if let Some(root) = explicit {
        return MarsContext::new(root.to_path_buf());
    }

    let cwd = std::env::current_dir()?;
    let mut dir = cwd.as_path();

    loop {
        for subdir in WELL_KNOWN.iter().chain(TOOL_DIRS.iter()) {
            let candidate = dir.join(subdir);
            if candidate.join("mars.toml").exists() {
                let ctx = MarsContext::new(candidate)?;
                // Validate: canonical root should be under the directory we found it in
                let expected_parent = dir.canonicalize().unwrap_or_else(|_| dir.to_path_buf());
                if !ctx.managed_root.starts_with(&expected_parent) {
                    return Err(MarsError::Config(ConfigError::Invalid {
                        message: format!(
                            "{}/{} resolves to {} which is outside {}. \
                             The managed root may be a symlink. Use --root to override.",
                            dir.display(), subdir, ctx.managed_root.display(),
                            expected_parent.display(),
                        ),
                    }));
                }
                return Ok(ctx);
            }
        }

        if dir.join("mars.toml").exists() {
            return MarsContext::new(dir.to_path_buf());
        }

        match dir.parent() {
            Some(parent) => dir = parent,
            None => break,
        }
    }

    // ... existing error ...
}
```

### `src/cli/check.rs` — symlink skip in scanning loops

In both the agent scanning loop and skill scanning loop, add symlink detection before processing:

```rust
// Agent loop (after sorting entries):
for entry in entries {
    let path = entry.path();
    // Skip symlinked entries — can't validate content we don't own
    if path.symlink_metadata()
        .map(|m| m.file_type().is_symlink())
        .unwrap_or(false)
    {
        warnings.push(format!(
            "skipping symlinked agent `{}` — cannot validate symlinked entries",
            path.file_name().unwrap_or_default().to_string_lossy()
        ));
        continue;
    }
    // ... existing processing ...
}
```

Same pattern for skill dirs.

### `src/cli/doctor.rs` — symlink skip in scanning loops

Same pattern as check.rs, in the agent and skill scanning sections of `run()`.

### `src/cli/link.rs` — `scan_dir_recursive()`

Add `.follow_links(false)` to the walkdir and handle symlink entries:

```rust
for entry in walkdir::WalkDir::new(target_subdir)
    .follow_links(false)
    .into_iter()
    .filter_map(|e| e.ok())
{
    let ft = entry.file_type();
    if ft.is_dir() {
        continue;
    }

    // Symlinks in target dir are treated as conflicts
    if ft.is_symlink() {
        let relative = match entry.path().strip_prefix(target_subdir) {
            Ok(r) => r.to_path_buf(),
            Err(_) => continue,
        };
        conflicts.push(ConflictInfo {
            relative_path: relative,
            target_desc: "symlink".to_string(),
            managed_desc: String::new(),
        });
        continue;
    }
    // ... existing file processing ...
}
```

## Dependencies

- Should run after Phase 1 (both touch doctor.rs, but different functions)
- Independent of Phase 2 and Phase 3

## Verification Criteria

- [ ] `cargo test` passes
- [ ] `cargo clippy --all-targets --all-features` clean  
- [ ] Add test: symlinked `.agents/` outside project tree → error from `find_agents_root`
- [ ] Add test: symlinked agent file in `agents/` → `mars check` warns and skips
- [ ] Add test: symlinked skill dir in `skills/` → `mars doctor` warns and skips
- [ ] Add test: symlink in link target dir → treated as conflict in scan
- [ ] Normal (non-symlink) operations unchanged
