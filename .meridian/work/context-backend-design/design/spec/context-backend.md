# Context Backend Behavioral Specification

## Purpose

Externalize business-sensitive context (`work/`, `work-archive/`) to private locations while keeping code documentation (`fs/`) in-repo.

---

## EARS Statements

### Configuration Resolution

**CTX-CFG-001**: When the system starts, it SHALL resolve context paths using the precedence: `meridian.local.toml` > `meridian.toml` > `~/.meridian/config.toml`.

**CTX-CFG-002**: When `[context.work]` is absent from all config files, the system SHALL default to `source = "local"` and `path = ".meridian/work"`.

**CTX-CFG-003**: When `[context.fs]` is absent from all config files, the system SHALL default to `source = "local"` and `path = ".meridian/fs"`.

**CTX-CFG-004**: When `context.work.path` starts with `.`, the system SHALL resolve it relative to the repo root.

**CTX-CFG-005**: When `context.work.path` starts with `~`, the system SHALL expand it relative to the user's home directory.

**CTX-CFG-006**: When `context.work.path` starts with `/`, the system SHALL treat it as an absolute path.

**CTX-CFG-007**: When `context.work.path` contains `{project}`, the system SHALL substitute the project UUID from `.meridian/id`.

**CTX-CFG-008**: When `context.work.source` is not `"local"` or `"git"`, the system SHALL reject the config with an error.

### Environment Variable Export

**CTX-ENV-001**: When a spawn launches with a work item active, the system SHALL set `MERIDIAN_WORK_DIR` to the resolved work path joined with the work item name.

**CTX-ENV-002**: When a spawn launches, the system SHALL set `MERIDIAN_FS_DIR` to the resolved fs path.

**CTX-ENV-003**: When `context.work.path` resolves to a non-existent directory, the system SHALL create it on first use.

**CTX-ENV-004**: When an arbitrary context `[context.<name>]` is configured, the system SHALL export `MERIDIAN_CONTEXT_<NAME>_DIR` (uppercase) for spawns.

**CTX-ENV-005**: The `work` context SHALL export as `MERIDIAN_WORK_DIR` (not `MERIDIAN_CONTEXT_WORK_DIR`) for backward compatibility.

**CTX-ENV-006**: The `fs` context SHALL export as `MERIDIAN_FS_DIR` (not `MERIDIAN_CONTEXT_FS_DIR`) for backward compatibility.

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

### Backward Compatibility

**CTX-COMPAT-001**: When no `[context]` section exists in any config file, the system SHALL behave identically to the pre-feature baseline.

**CTX-COMPAT-002**: When `MERIDIAN_WORK_DIR` is set explicitly in the environment, it SHALL override config-based resolution.

**CTX-COMPAT-003**: When `MERIDIAN_FS_DIR` is set explicitly in the environment, it SHALL override config-based resolution.

### Extensibility

**CTX-EXT-001**: When `[context.<name>]` is present for any name other than `work` or `fs`, the system SHALL parse it as a context with `source` and `path` fields.

**CTX-EXT-002**: When the user runs `meridian context sync <name>` for an arbitrary context with `source = "git"`, the system SHALL sync that context.

---

## Acceptance Criteria

1. Zero config produces current behavior — no regressions
2. Single `~/.meridian/config.toml` with `source = "git"` externalizes work for all repos
3. Git sync operations never block on failure
4. Conflict markers are preserved and visible, never silently dropped
5. `meridian context` output is minimal — just `<name>: <resolved-path>` per line
6. `meridian context <name>` outputs just the path, suitable for scripting/agents
