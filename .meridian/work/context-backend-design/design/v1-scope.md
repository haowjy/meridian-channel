# Context Backend v1 — Simplified Scope

Single user, iterate fast, fix forward.

## What's In

- **Path configuration**: `[context.work]` and `[context.kb]` in config
- **Path resolution**: `~`, `{project}`, relative, absolute
- **`meridian context`**: Show resolved paths (replaces current behavior)
- **`meridian context mv <name> <dest>`**: Move context + update `meridian.local.toml`
- **`meridian context sync <name>`**: Git pull/push (if `source=git`)
- **`fs/` → `kb/` rename**: Auto-migration on startup
- **Legacy fallback**: `MERIDIAN_FS_DIR` as alias, `fs/` fallback with warning
- **Git sync warnings**: Contextual, non-blocking (not a repo, no remote, etc.)

## What's Out (Deferred)

- **`work-archive/` externalization**: Future restructure to `work/active/` + `work/archive/`
- **Elaborate two-phase migration**: Just move files, trust it works
- **Pre-migration backup with checksums**: Manual backup if paranoid
- **Crash recovery infrastructure**: Manual recovery (see below)
- **Command blocking on pending migration**: Just run migrations
- **Windows path edge cases**: POSIX-first, fix Windows issues as they arise
- **Arbitrary context validation**: Trust config is correct

## Prerequisite

- **`meridian.local.toml` support**: Add to config loader before this work

---

## Manual Recovery

### If `meridian context mv` crashes mid-move

**Symptoms**: Files split between source and destination

**Recovery**:
```bash
# Check what's where
ls -la .meridian/work/
ls -la ~/new/path/

# Option 1: Complete the move manually
mv .meridian/work/* ~/new/path/
rmdir .meridian/work

# Option 2: Abort and restore
mv ~/new/path/* .meridian/work/
rmdir ~/new/path

# Then fix config
vim meridian.local.toml  # set correct path
```

### If git sync leaves conflicts

**Symptoms**: Files have `<<<<<<<` markers

**Recovery**:
```bash
cd ~/context/work
git status                    # see conflicted files
vim <conflicted-file>         # resolve manually
git add . && git commit -m "resolved"
git push
```

### If `fs/` auto-migration fails

**Symptoms**: Both `.meridian/fs/` and `.meridian/kb/` exist

**Recovery**:
```bash
# Check contents
ls -la .meridian/fs/
ls -la .meridian/kb/

# Merge manually (kb/ wins)
cp -rn .meridian/fs/* .meridian/kb/
rm -rf .meridian/fs/
```

### If config is broken

**Symptoms**: Meridian can't find context paths

**Recovery**:
```bash
# Check what config says
cat meridian.local.toml
cat meridian.toml
cat ~/.meridian/config.toml

# Fix or remove the broken entry
vim meridian.local.toml

# Or nuke and start fresh
rm meridian.local.toml
# contexts revert to defaults
```

---

## Design Decisions (Summary)

| Decision | Choice | Why |
|----------|--------|-----|
| CLI surface | `meridian context mv` | Terraform-style, familiar |
| Config file | `meridian.local.toml` | Gitignored, project-local |
| Migration safety | Simple move, manual recovery | Single user, fix forward |
| Git sync | Built-in, optional | Power user feature, future paid tier |
| `work-archive` | Deferred | Restructure later |
| Windows | Best effort | Fix issues as they arise |

---

## Future Work

1. **Work restructure**: `work/active/` + `work/archive/` under single `work/` root
2. **Meridian Sync**: Paid managed sync service (`source = "meridian"`)
3. **Windows hardening**: Drive letters, UNC paths, cross-volume moves
4. **Multi-user safety**: Locking, proper two-phase migration
