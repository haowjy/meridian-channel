# Context Backend Behavioral Specification

## Purpose

Externalize business-sensitive context (`work/`, `work-archive/`) to private locations. The knowledge base (`kb/`) is the persistent agent memory layer — accumulated learnings, codebase understanding, decision history.

---

## EARS Statements

### Configuration Resolution

**CTX-CFG-001**: When the system starts, it SHALL resolve context paths using the precedence: `meridian.local.toml` > `meridian.toml` > `~/.meridian/config.toml`.

**CTX-CFG-002**: When `[context.work]` is absent from all config files, the system SHALL default to `source = "local"` and `path = ".meridian/work"`.

**CTX-CFG-003**: When `[context.kb]` is absent from all config files, the system SHALL default to `source = "local"` and `path = ".meridian/kb"`.

**CTX-CFG-004**: When `context.*.path` starts with `.`, the system SHALL resolve it relative to the repo root.

**CTX-CFG-005**: When `context.*.path` starts with `~`, the system SHALL expand it relative to the user's home directory.

**CTX-CFG-006**: When `context.*.path` starts with `/`, the system SHALL treat it as an absolute path.

**CTX-CFG-007**: When `context.*.path` contains `{project}`, the system SHALL substitute the project UUID from `.meridian/id`.

**CTX-CFG-008**: When `context.*.source` is not a recognized value, the system SHALL reject the config with an error.

### Source Types

**CTX-SRC-001**: When `source = "local"`, the system SHALL treat the path as a local directory with no sync behavior.

**CTX-SRC-002**: When `source = "git"`, the system SHALL auto-register the `git-autosync` hook for that context.

**CTX-SRC-003**: When `source = "git"`, the system SHALL discover the git repo root by walking up from the resolved context path to the nearest parent containing `.git/`.

**CTX-SRC-004**: When `source = "git"` AND no parent git repo is found for the resolved context path, the system SHALL fail with an actionable error.

**CTX-SRC-005**: When `git-autosync` stages changes for a git-backed context, it SHALL run `git add .` with `cwd` set to that context path to scope staging to that subtree.

### Environment Variable Export

**CTX-ENV-001**: When a spawn launches with a work item active, the system SHALL set `MERIDIAN_WORK_DIR` to the resolved work path joined with the work item name.

**CTX-ENV-002**: When a spawn launches, the system SHALL set `MERIDIAN_KB_DIR` to the resolved kb path.

**CTX-ENV-003**: When `context.*.path` resolves to a non-existent directory, the system SHALL create it on first use.

**CTX-ENV-004**: When an arbitrary context `[context.<name>]` is configured, the system SHALL export `MERIDIAN_CONTEXT_<NAME>_DIR` (uppercase) for spawns.

**CTX-ENV-005**: The `work` context SHALL export as `MERIDIAN_WORK_DIR` (not `MERIDIAN_CONTEXT_WORK_DIR`).

**CTX-ENV-006**: The `kb` context SHALL export as `MERIDIAN_KB_DIR` (not `MERIDIAN_CONTEXT_KB_DIR`).

### CLI Surface

**CTX-CLI-001**: When the user runs `meridian context`, the system SHALL display each context name, resolved path, and source type.

**CTX-CLI-002**: When the user runs `meridian context <name>`, the system SHALL output only the resolved absolute path (no label).

**CTX-CLI-003**: When the user runs `meridian context --verbose`, the system SHALL display source, path spec, and resolved path for each context.

### Migration

**CTX-MIG-001**: When `.meridian/fs/` exists AND `.meridian/kb/` does not exist, the system SHALL use `.meridian/fs/` as the kb path (graceful fallback).

**CTX-MIG-002**: When both `.meridian/fs/` and `.meridian/kb/` exist, the system SHALL use `.meridian/kb/` and log a warning about the orphaned `fs/` directory.

### Backward Compatibility

**CTX-COMPAT-001**: When no `[context]` section exists in any config file, the system SHALL behave identically to the pre-feature baseline.

**CTX-COMPAT-002**: When `MERIDIAN_WORK_DIR` is set explicitly in the environment, it SHALL override config-based resolution.

**CTX-COMPAT-003**: When `MERIDIAN_KB_DIR` is set explicitly in the environment, it SHALL override config-based resolution.

**CTX-COMPAT-004**: When `MERIDIAN_FS_DIR` is set explicitly in the environment, the system SHALL treat it as an alias for `MERIDIAN_KB_DIR` (deprecated warning).

---

## Context Model

| Context | Always Present | Default Path | Env Var | Purpose |
|---------|---------------|--------------|---------|---------|
| `work` | ✓ | `.meridian/work` | `MERIDIAN_WORK_DIR` | Ephemeral work-item context |
| `kb` | ✓ | `.meridian/kb` | `MERIDIAN_KB_DIR` | Persistent agent memory |
| Arbitrary | ✗ | (must configure) | `MERIDIAN_CONTEXT_<NAME>_DIR` | User-defined contexts |

---

## Acceptance Criteria

1. Zero config produces current behavior — `work` and `kb` at `.meridian/`
2. `source = "git"` auto-registers `git-autosync` hook
3. Git-backed contexts discover repo roots from their configured paths (no explicit `remote` field required)
4. `meridian context` output shows resolved paths with source type
5. `meridian context <name>` outputs just the path, suitable for scripting
6. Both `work` and `kb` are always present even with zero config
7. Legacy `.meridian/fs/` works via fallback with deprecation warning
