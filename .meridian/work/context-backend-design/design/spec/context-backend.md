# Context Backend Behavioral Specification

## Purpose

Externalize business-sensitive context (`work/`, `work-archive/`) to private locations. The knowledge base (`kb/`) is the persistent agent memory layer — accumulated learnings, codebase understanding, decision history.

---

## EARS Statements

### Configuration Resolution

**CTX-CFG-001**: When the system starts, it SHALL resolve context paths using the precedence: `meridian.local.toml` > `meridian.toml` > `~/.meridian/config.toml`.

**CTX-CFG-002**: When `[context.work]` is absent from all config files, the system SHALL default to `source = "local"` and `path = ".meridian/work"`.

**CTX-CFG-003**: When `[context.kb]` is absent from all config files, the system SHALL default to `source = "local"` and `path = ".meridian/kb"`.

**CTX-CFG-004**: When `context.work.path` starts with `.`, the system SHALL resolve it relative to the repo root.

**CTX-CFG-005**: When `context.work.path` starts with `~`, the system SHALL expand it relative to the user's home directory.

**CTX-CFG-006**: When `context.work.path` starts with `/`, the system SHALL treat it as an absolute path.

**CTX-CFG-007**: When `context.work.path` contains `{project}`, the system SHALL substitute the project UUID from `.meridian/id`.

**CTX-CFG-008**: When `context.work.source` is not `"local"` or `"git"`, the system SHALL reject the config with an error.

### Environment Variable Export

**CTX-ENV-001**: When a spawn launches with a work item active, the system SHALL set `MERIDIAN_WORK_DIR` to the resolved work path joined with the work item name.

**CTX-ENV-002**: When a spawn launches, the system SHALL set `MERIDIAN_KB_DIR` to the resolved kb path.

**CTX-ENV-003**: When `context.work.path` resolves to a non-existent directory, the system SHALL create it on first use.

**CTX-ENV-004**: When an arbitrary context `[context.<name>]` is configured, the system SHALL export `MERIDIAN_CONTEXT_<NAME>_DIR` (uppercase) for spawns.

**CTX-ENV-005**: The `work` context SHALL export as `MERIDIAN_WORK_DIR` (not `MERIDIAN_CONTEXT_WORK_DIR`).

**CTX-ENV-006**: The `kb` context SHALL export as `MERIDIAN_KB_DIR` (not `MERIDIAN_CONTEXT_KB_DIR`).

**CTX-ENV-007**: When `context.kb.path` resolves to a non-existent directory, the system SHALL create it on first use.

### Git Sync Layer

**CTX-GIT-001**: When `source = "git"` AND `auto_pull = true` AND a session starts, the system SHALL execute `git pull --rebase` in the context directory.

**CTX-GIT-002**: When `source = "git"` AND `auto_commit = true` AND a work item is written, the system SHALL execute `git add . && git commit -m "work: <item>"` in the context directory.

**CTX-GIT-003**: When `source = "git"` AND `auto_push = true` AND a commit succeeds, the system SHALL execute `git push` in the context directory.

**CTX-GIT-004**: When `git pull --rebase` results in a conflict, the system SHALL commit the file with conflict markers and push, preserving both sides.

**CTX-GIT-005**: When git sync fails due to network error, the system SHALL log a warning and continue operation without blocking the session.

**CTX-GIT-006**: When `source = "git"` AND the context directory is not a git repository, the system SHALL skip sync operations with a warning.

**CTX-GIT-007**: When `source = "local"`, the system SHALL ignore all git-related options.

### CLI Surface

**CTX-CLI-001**: When the user runs `meridian context`, the system SHALL display each context name and its resolved absolute path, one per line (format: `<name>: <path>`).

**CTX-CLI-002**: When the user runs `meridian context <name>`, the system SHALL output only the resolved absolute path for that context (no label, no newline prefix).

**CTX-CLI-003**: When the user runs `meridian context --verbose`, the system SHALL display source, path spec, resolved path, and sync status for each context.

**CTX-CLI-004**: When the user runs `meridian context sync <name>`, the system SHALL execute pull then push for that context.

**CTX-CLI-005**: When the user runs `meridian context sync <name> --pull`, the system SHALL execute only pull.

**CTX-CLI-006**: When the user runs `meridian context sync <name> --push`, the system SHALL execute only push.

**CTX-CLI-007**: When `source = "local"` AND the user runs `meridian context sync <name>`, the system SHALL report "source is local, nothing to sync" and exit 0.

**CTX-CLI-008**: When the user runs `meridian context`, the system SHALL display all configured contexts including arbitrary ones.

### Migration

**CTX-MIG-001**: When a user sets `context.work.path` to a new path AND the old path contains data, the system SHALL NOT automatically migrate data.

**CTX-MIG-002**: When the user runs `meridian context migrate <name>`, the system SHALL move old path contents to the configured path.

**CTX-MIG-003**: When the configured path already contains data AND the user runs `meridian context migrate <name>`, the system SHALL refuse with "destination not empty" and exit 1.

**CTX-MIG-004**: When migration completes successfully, the system SHALL remove the original directory.

### Legacy fs/ Detection

**CTX-MIG-005**: When the system starts AND `.meridian/fs/` exists, the system SHALL log a warning: "Detected .meridian/fs/ (deprecated). Rename to .meridian/kb/ to upgrade."

**CTX-MIG-006**: When `.meridian/fs/` exists AND `.meridian/kb/` does not exist, the system SHALL use `.meridian/fs/` as the kb path (graceful fallback).

**CTX-MIG-007**: When both `.meridian/fs/` and `.meridian/kb/` exist, the system SHALL use `.meridian/kb/` and log a warning about the orphaned `fs/` directory.

### Backward Compatibility

**CTX-COMPAT-001**: When no `[context]` section exists in any config file, the system SHALL behave identically to the pre-feature baseline (using `.meridian/work` and `.meridian/kb`).

**CTX-COMPAT-002**: When `MERIDIAN_WORK_DIR` is set explicitly in the environment, it SHALL override config-based resolution.

**CTX-COMPAT-003**: When `MERIDIAN_KB_DIR` is set explicitly in the environment, it SHALL override config-based resolution.

**CTX-COMPAT-004**: When `MERIDIAN_FS_DIR` is set explicitly in the environment, the system SHALL treat it as an alias for `MERIDIAN_KB_DIR` (deprecated warning).

### Extensibility

**CTX-EXT-001**: When `[context.<name>]` is present for any name other than `work` or `kb`, the system SHALL parse it as a context with `source` and `path` fields.

**CTX-EXT-002**: When the user runs `meridian context sync <name>` for an arbitrary context with `source = "git"`, the system SHALL sync that context.

---

## Context Model

| Context | Always Present | Default Path | Env Var | Purpose |
|---------|---------------|--------------|---------|---------|
| `work` | ✓ | `.meridian/work` | `MERIDIAN_WORK_DIR` | Ephemeral work-item context (design, plans, decisions) |
| `kb` | ✓ | `.meridian/kb` | `MERIDIAN_KB_DIR` | Persistent agent memory (learnings, codebase knowledge) |
| Arbitrary | ✗ | (must configure) | `MERIDIAN_CONTEXT_<NAME>_DIR` | User-defined contexts |

---

## Acceptance Criteria

1. Zero config produces current behavior — `work` and `kb` at `.meridian/`
2. Single `~/.meridian/config.toml` with `source = "git"` externalizes contexts for all repos
3. Git sync operations never block on failure
4. Conflict markers are preserved and visible, never silently dropped
5. `meridian context` output is minimal — just `<name>: <resolved-path>` per line
6. `meridian context <name>` outputs just the path, suitable for scripting/agents
7. Both `work` and `kb` are always present even with zero config
8. Legacy `.meridian/fs/` works via fallback with deprecation warning

---

## Migration Framework Integration

**CTX-MIG-008**: The `fs → kb` rename SHALL be implemented as migration `v002_fs_to_kb` in the existing `migrations/` framework.

**CTX-MIG-009**: Migration `v002_fs_to_kb` SHALL have `mode = "auto"` in the registry, indicating it runs automatically on detection.

**CTX-MIG-010**: When auto-migration succeeds, the system SHALL log: "Auto-migrated: v002_fs_to_kb".

**CTX-MIG-011**: When auto-migration cannot run (both `fs/` and `kb/` exist), the system SHALL fall back to the legacy fs/ detection behavior (CTX-MIG-005 through CTX-MIG-007).

---

## Migration Safety Requirements

### Two-Phase Commit

**CTX-MIG-012**: When a migration runs, it SHALL write transformed data to `.migration-staging/` before committing.

**CTX-MIG-013**: When staging completes successfully, the migration SHALL atomically move staged files to final locations.

**CTX-MIG-014**: When staging fails, the migration SHALL clean up `.migration-staging/` and report failure without modifying target paths.

### Pre-Migration Backup

**CTX-MIG-015**: Before mutating files, the migration SHALL create a backup in `.migration-backup/<migration-id>/` with checksums.

**CTX-MIG-016**: When migration succeeds, the system MAY retain or remove the backup based on configuration.

### Crash Recovery

**CTX-MIG-017**: When `.migration-staging/` exists on startup, the system SHALL detect incomplete migration from `intent.json`.

**CTX-MIG-018**: When an incomplete auto-migration is detected, the system SHALL re-run it automatically.

**CTX-MIG-019**: When an incomplete manual-migration is detected, the system SHALL prompt user with `meridian migrate doctor`.

### Command Blocking

**CTX-MIG-020**: When a manual-migration is pending, write commands (`spawn`, `sync`, `work start`) SHALL fail with remediation guidance.

**CTX-MIG-021**: When a migration is pending, read commands (`status`, `show`, `context`) SHALL continue to work for diagnosis.

**CTX-MIG-022**: When a migration is pending, the system SHALL show the exact command to run for remediation.

---

## Migration Command (Revised)

**CTX-MIG-023**: When the user runs `meridian context migrate <name> <destination>`, the system SHALL move contents from the current resolved path to `<destination>`.

**CTX-MIG-024**: When migration completes, the system SHALL update `meridian.local.toml` with `[context.<name>] path = "<destination>"`.

**CTX-MIG-025**: The migrate command SHALL NOT set or modify the `source` field — only `path`.

**CTX-MIG-026**: When checking "destination not empty", the system SHALL ignore hidden metadata files (`.git/`, `.DS_Store`, `.gitkeep`).

**CTX-MIG-027**: The migrate command SHALL NOT perform any git operations (no init, commit, or push).

---

## Git Sync Warnings (Contextual, Non-Blocking)

**CTX-GIT-008**: When `source = "git"` AND the context directory is not a git repository, the system SHALL warn once per session: "context.<name> has source = git but <path> is not a git repository. Git sync disabled."

**CTX-GIT-009**: When `auto_pull = true` AND `git pull` fails due to no remote configured, the system SHALL warn: "git pull failed for context.<name> — no remote configured. Skipping sync."

**CTX-GIT-010**: When `auto_push = true` AND `git push` fails due to no remote configured, the system SHALL warn: "git push failed for context.<name> — no remote configured. Skipping sync."

**CTX-GIT-011**: All git sync warnings SHALL be non-blocking — the system continues normal operation after logging the warning.

**CTX-GIT-012**: Git sync warnings SHALL include actionable remediation hints (e.g., "Run 'git init' in <path>" or "Run 'git remote add origin <url>'").

---

## Product Positioning

### Sync Tiers

| Tier | Source | Who Syncs | Status |
|------|--------|-----------|--------|
| **Local** | `source = "local"` (default) | User (Dropbox, iCloud, OneDrive, manual) | v1 |
| **Git** | `source = "git"` | User's git repo, meridian automates push/pull | v1 |
| **Meridian Sync** | `source = "meridian"` | Managed service, zero config | Future (paid) |

### Documentation Note

README should mention: "For zero-config sync, place your context folder in Dropbox, iCloud, OneDrive, or Google Drive. Meridian doesn't care how the folder syncs — it just reads and writes files."

This follows the Obsidian model: contexts are just folders, user decides how to sync them.
