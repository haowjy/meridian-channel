# Context Backend Refactor Agenda

## REF-CTX-001: Rename fs to kb Throughout Codebase

**Current state**: Code and docs use `fs_dir`, `MERIDIAN_FS_DIR`, `.meridian/fs/`.

**Target state**: `kb_dir`, `MERIDIAN_KB_DIR`, `.meridian/kb/` with `MERIDIAN_FS_DIR` as deprecated alias.

**Files to change**:
- `src/meridian/lib/state/paths.py` — `fs_dir` → `kb_dir`, `.gitignore` entries
- `src/meridian/lib/launch/env.py` — env var normalization
- `src/meridian/lib/ops/context.py`, `manifest.py`, `config.py`
- `src/meridian/cli/misc_commands.py`
- `src/meridian/lib/state/__init__.py`
- `src/meridian/lib/launch/reference.py`
- `docs/configuration.md`, `docs/_internal/*.md`

**Agent prompt updates** (separate commits to source repos):
- `meridian-cli` skill
- `dev-artifacts` skill
- `meridian-work-coordination` skill
- `docs-orchestrator` agent
- `code-documenter` agent
- `agent-staffing/resources/maintainers.md`

**Risk**: Medium — breaking rename, but pre-1.0 and `MERIDIAN_FS_DIR` alias mitigates.

---

## REF-CTX-002: Extract Path Resolution from StatePaths

**Current state**: `StatePaths.from_root_dir()` hardcodes `kb_dir = root_dir / "kb"` and `work_dir = root_dir / "work"`.

**Target state**: Path resolution delegates to context resolver when config is present, falls back to hardcoded paths when absent.

**Approach**: 
1. Create `resolve_context()` function that takes repo_root + config
2. Modify `resolve_repo_state_paths()` to accept optional `ContextConfig`
3. When config absent, behavior unchanged
4. When config present, use resolved paths from config

**Risk**: Low — additive change with fallback to current behavior.

---

## REF-CTX-003: Unify Environment Variable Normalization

**Current state**: `_normalize_meridian_kb_dir()` and `_normalize_meridian_work_dir()` in `env.py` resolve paths independently using `resolve_repo_state_paths()`.

**Target state**: Both functions use the same context resolver, ensuring config-based paths are consistent.

**Approach**:
1. Create `resolve_spawn_context()` that returns both paths
2. Modify `_normalize_meridian_env()` to call resolver once
3. Both env vars set from same resolution
4. Add `MERIDIAN_FS_DIR` → `MERIDIAN_KB_DIR` alias handling

**Risk**: Low — consolidation of existing logic.

---

## REF-CTX-004: Add Context Section to Config Loader

**Current state**: `settings.py` parses `[defaults]`, `[timeouts]`, `[harness]`, `[primary]`, `[output]` sections.

**Target state**: Add `[context]` section parsing with `work` and `kb` sub-tables, plus arbitrary contexts.

**Approach**:
1. Add `ContextConfig` to `MeridianConfig` model
2. Extend `_normalize_toml_payload()` to handle `[context]` section
3. Add validation for path spec format
4. Support `__pydantic_extra__` for arbitrary contexts

**Risk**: Low — additive to existing config infrastructure.

---

## REF-CTX-005: Create context Module

**Current state**: No `src/meridian/lib/context/` directory.

**Target state**: New module with:
- `resolver.py` — path resolution logic
- `git_sync.py` — git sync operations
- `__init__.py` — public exports

**Risk**: None — new code.

---

## REF-CTX-006: Add Context CLI Command Group

**Current state**: No `meridian context` command.

**Target state**: New command group with `show`, `sync`, `migrate` subcommands.

**Approach**:
1. Create `context_cmd.py` with click group
2. Register in `main.py` command tree
3. Wire to ops functions

**Risk**: None — new code.

---

## Sequencing

1. **REF-CTX-001** (rename fs→kb) — foundational, do first
2. **REF-CTX-004** (config schema) — no dependencies on rename, enables all else
3. **REF-CTX-005** (context module) — no dependencies, pure addition
4. **REF-CTX-002** (path resolution) — depends on 001, 004, 005
5. **REF-CTX-003** (env normalization) — depends on 002
6. **REF-CTX-006** (CLI) — depends on 002, 005

Phase 1: REF-CTX-001
Phase 2: REF-CTX-004, REF-CTX-005 (parallel)
Phase 3: REF-CTX-002, REF-CTX-003, REF-CTX-006 (sequential)

---

## REF-CTX-007: Add Legacy fs/ Detection and Fallback

**Current state**: Users with existing `.meridian/fs/` directories would need to manually rename.

**Target state**: Detection + warning + graceful fallback when legacy fs/ exists.

**Approach**:
1. Create `src/meridian/lib/context/compat.py`
2. Add `resolve_kb_path_with_fallback()` function
3. Use fs/ as kb path if kb/ does not exist, warn user
4. Handle MERIDIAN_FS_DIR as deprecated alias for MERIDIAN_KB_DIR

**Risk**: Low — read-only detection, no mutations.

**Sequencing**: Run as part of REF-CTX-001 (the rename refactor).

---

## REF-CTX-008: Add Migration Mode to Registry Schema

**Current state**: `registry.toml` has `status` field but no `mode` field.

**Target state**: Add `mode = "auto" | "manual"` field to registry schema.

**Approach**:
1. Update `registry.toml` schema to include `mode`
2. Add `mode = "auto"` to v002 entry
3. Implement `run_auto_migrations()` in state initialization

**Risk**: Low — additive schema change.

---

## REF-CTX-009: Housekeeping — migrations/CLAUDE.md

**Current state**: `migrations/` has `AGENTS.md` but no `CLAUDE.md`.

**Target state**: Add `migrations/CLAUDE.md` with content: `@AGENTS.md`

**Risk**: None — trivial addition.

---

## REF-CTX-010: Add Two-Phase Migration Infrastructure

**Current state**: Migrations write directly to target paths.

**Target state**: Migrations write to `.migration-staging/` first, then atomic commit.

**Approach**:
1. Add `stage_migration()` helper that writes to staging dir
2. Add `commit_migration()` helper that atomically moves staged files
3. Add `intent.json` format for crash recovery
4. Update existing v001 and new v002 to use two-phase pattern

**Risk**: Low — improves safety, no behavior change for successful migrations.

---

## REF-CTX-011: Add Pre-Migration Backup

**Current state**: No backup before migration.

**Target state**: Backup created in `.migration-backup/<id>/` with manifest and checksums.

**Approach**:
1. Add `backup_for_migration()` helper
2. Create manifest.json with original paths and checksums
3. Copy files to backup directory before mutation
4. Configurable: retain or delete backup after success

**Risk**: Low — additive safety mechanism.

---

## REF-CTX-012: Add Migration Command Blocking

**Current state**: No check for pending migrations on command startup.

**Target state**: Write commands blocked when manual migration pending; read commands allowed.

**Approach**:
1. Add `check_pending_migrations()` to CLI startup
2. For manual-pending: block write commands with clear error
3. For auto-pending: run auto-migrations before proceeding
4. Read commands always allowed

**Risk**: Low — improves UX and safety.

---

## REF-CTX-013: Create v002_fs_to_kb Migration

**Current state**: No migration for fs→kb rename.

**Target state**: `migrations/v002_fs_to_kb/` with check.py, migrate.py, README.md.

**Approach**:
1. Create migration directory structure
2. Implement check.py (detect fs/ exists, kb/ doesn't)
3. Implement migrate.py (atomic rename, update .gitignore)
4. Add entry to registry.toml with `mode = "auto"`
5. Add README.md documenting the migration

**Risk**: Low — follows established migration patterns.

---

## REF-CTX-014: Update migrations/AGENTS.md with Safety Principles

**Current state**: AGENTS.md has basic principles.

**Target state**: AGENTS.md includes:
- Auto vs manual migration modes
- Two-phase commit pattern
- Pre-migration backup guidance
- Crash recovery detection
- UX guidelines (block write, allow read)

**Status**: DONE — already updated in this design session.

**Risk**: None — documentation only.

---

## REF-CTX-015: Agent Prompt Updates (Separate Repos)

**Current state**: Agent prompts reference `$MERIDIAN_FS_DIR` and `fs/`.

**Target state**: Updated to `$MERIDIAN_KB_DIR` and `kb/`.

**Scope**: This is a FOLLOW-UP task in separate repos:
- `meridian-flow/meridian-base`: meridian-cli, dev-artifacts, meridian-work-coordination skills
- `meridian-flow/meridian-dev-workflow`: docs-orchestrator, code-documenter agents

**Approach**:
1. After meridian-cli v0.1.0 ships with kb support
2. Update prompts in source repos
3. Commit and push
4. `meridian mars sync` to regenerate .agents/

**Risk**: Low — documentation updates only.

---

## Complete Sequencing

### Phase 1: Foundation
- **REF-CTX-009**: Add migrations/CLAUDE.md ✓ (done)
- **REF-CTX-014**: Update migrations/AGENTS.md ✓ (done)

### Phase 2: Migration Infrastructure (parallel)
- **REF-CTX-008**: Add migration mode to registry schema
- **REF-CTX-010**: Add two-phase migration infrastructure
- **REF-CTX-011**: Add pre-migration backup
- **REF-CTX-012**: Add migration command blocking

### Phase 3: fs→kb Rename
- **REF-CTX-001**: Rename fs to kb throughout codebase
- **REF-CTX-007**: Add legacy fs/ detection and fallback
- **REF-CTX-013**: Create v002_fs_to_kb migration

### Phase 4: Context Config (parallel)
- **REF-CTX-004**: Add context section to config loader
- **REF-CTX-005**: Create context module (resolver, git_sync)

### Phase 5: Integration
- **REF-CTX-002**: Extract path resolution from StatePaths
- **REF-CTX-003**: Unify environment variable normalization

### Phase 6: CLI
- **REF-CTX-006**: Add context CLI command group

### Follow-up (separate repos, after release)
- **REF-CTX-015**: Agent prompt updates

---

## REF-CTX-016: Migrate Command with Destination Argument

**Current state**: Original design had `meridian context migrate <name>` pulling destination from config.

**Target state**: `meridian context migrate <name> <destination>` — explicit destination, updates config after move.

**Approach**:
1. Command takes context name and destination path
2. Resolves current path from config/defaults
3. Moves contents to destination
4. Updates `meridian.local.toml` with new path (not source)
5. Ignores metadata files when checking "not empty"

**Risk**: Low — clearer UX than original design.

---

## REF-CTX-017: Git Warning System

**Current state**: Design mentions warnings but doesn't specify when/how.

**Target state**: Contextual warnings at operation time, not upfront validation.

**Implementation points**:
- `check_git_repo_status()` called before git operations
- Warnings to stderr, include remediation hints
- Once-per-session for "not a git repo" warning
- Per-operation for pull/push failures

**Risk**: Low — improves UX without changing core behavior.
