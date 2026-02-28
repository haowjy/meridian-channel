# Meridian-Channel: Technical Debt Cleanup Inventory

**Purpose**: Explicitly document deprecated code and features that should be removed during the implementation of the file-based architecture.

This document serves as a practical reference for developers during Phase 1-3 implementation. Each section includes file paths, line numbers, and removal priority.

---

## 1. Deprecated Features to Remove

### 1.1 `--skills` CLI Flag (Priority: HIGH)

**Why Remove**: Agent profiles now own skills statically; skills should not be passed per-run via CLI.

**Files to Remove**:

#### src/meridian/cli/run.py
- **Lines 52-59**: Parameter definition for `skill_flags`
  ```python
  skill_flags: Annotated[
      tuple[str, ...],
      Parameter(
          name=["--skills", "-s"],
          help="Skill names to load (repeatable).",
          negative_iterable=(),
      ),
  ] = (),
  ```
- **Line 157**: Remove `skills=skill_flags` from `RunCreateInput()`
- **Lines 177-184**: Remove KeyError handler for `unknown_skills` error

#### src/meridian/lib/ops/_run_prepare.py
- **Line 258**: Comment mentioning `--skills` flag (update or remove)
- Search for all skill-resolution logic that depends on CLI flags

#### Tests
- `/home/jimyao/gitrepos/meridian-collab/meridian-channel/tests/test_cli_ux_fixes.py` — Remove all `--skills` flag tests
- `/home/jimyao/gitrepos/meridian-collab/meridian-channel/tests/test_flag_strategy.py` — Remove all `--skills` flag validation tests

#### Documentation
- `docs/cli-reference.md` — Remove `--skills` documentation

**Replacement Path**: Users should edit agent profiles to define skills instead of passing via CLI.

**Rollback Strategy**: None needed (breaking change, documented in release notes).

---

### 1.2 SQLite as Authoritative State for Spaces (Priority: HIGH)

**Why Remove**: Markdown files (`space.md`) become the source of truth; SQLite becomes an optional read-only index.

**Files Affected**:

#### src/meridian/lib/state/schema.py
- **Lines 29-48**: `CREATE TABLE spaces` definition in `_migration_001_init()`
  - Columns to deprecate: `description`, `plan_file`, `labels`, `supervisor_model`, `supervisor_harness`, `supervisor_harness_session_id`, `summary_path`
  - Columns to keep (minimal): `id`, `status`, `started_at`, `last_activity_at`, `finished_at`, `total_runs`, `total_cost_usd` (for aggregates only)
- **Lines 140-141**: Indexes on spaces table (may become unnecessary if only used as index)

#### src/meridian/lib/adapters/sqlite.py
- **Line 468+**: `create_space()` method — will need refactoring to read from files instead
- **Line 497+**: `get_space()` method — refactor to read space.md as primary source
- **Lines 965, 968**: Async wrappers for space CRUD (may need to refactor or remove)

**Rollback Strategy**:
- Option A: Keep SQLite tables but mark read-only with deprecation warnings
- Option B: Provide migration script to export SQLite spaces to `.meridian/<space-id>/space.md`
- Recommendation: Option A for 1 release, then Option B in next release

---

### 1.3 Space Read/Write CLI Commands (Priority: MEDIUM → HIGH in Phase 2)

**Why Remove**: These become `meridian fs` commands (read entire files, not custom space read/write).

**Files to Refactor**:

#### src/meridian/cli/space.py
- **Lines 129-149**: `_space_write()` function — migrate to `fs write`
- **Lines 152-167**: `_space_read()` function — migrate to `fs read`
- **Lines 170-177**: `_space_files()` function — migrate to `fs ls`

These commands should be deprecated in Phase 1 and removed in Phase 2 after `meridian fs` commands are available.

#### src/meridian/lib/ops/space.py
- **Lines 75-80**: `SpaceWriteInput` dataclass — migrate to fs operations
- **Lines 82-86**: `SpaceReadInput` dataclass — migrate to fs operations
- **Lines 89-92**: `SpaceFilesInput` dataclass — migrate to fs operations
- Search for `space_read_sync()`, `space_write_sync()`, `space_files_sync()` implementations

**Replacement Path**:
```bash
# Old (will be removed)
meridian space read <name> --session <session-id>
meridian space write <name> --content <content> --session <session-id>
meridian space files --session <session-id>

# New (Phase 2+)
meridian fs read <path> --session <session-id>
meridian fs write <path> --content <content> --session <session-id>
meridian fs ls <dir> --session <session-id>
```

**Rollback Strategy**: Deprecation warnings in Phase 1, removal in Phase 2.

---

### 1.4 Session-Scoped File Storage (Priority: TBD)

**Why Unclear**: Need design decision: are session files part of space filesystem or separate?

**Files to Review**:

#### src/meridian/lib/space/session_files.py
- **Full file**: Determines if session files are:
  - Part of `.meridian/<space-id>/fs/` (integrate into space filesystem)
  - Separate in `.meridian/<space-id>/sessions/` (keep separate)

**Decision Needed Before Removal**:
- [ ] Are session files part of space filesystem?
- [ ] Do they need separate lifecycle management?
- [ ] What's the user expectation for cleanup?

**Placeholder**: Keep this file for now, but clarify in design review before Phase 2.

---

### 1.5 Skill Composition Machinery (Priority: MEDIUM)

**Why Remove**: Skills are now static from agent profiles; no per-run composition needed.

**Files to Search**:

#### src/meridian/lib/prompt/compose.py
- **Lines 35-42**: `_render_skill_blocks()` function — may simplify if skills are just concatenated now
- **Lines 50-71**: `compose_run_prompt()` function — should load skills from agent profile, not compose them

Look for any logic that:
- Merges skills from multiple sources
- Reorders skills per run
- Filters skills by type

**Replacement Path**: Skills are loaded once from agent profile; no composition pipeline needed.

---

## 2. Code Patterns to Eliminate

### 2.1 Two-Source-of-Truth Pattern (SQLite + JSON/Files)

**Pattern**: State stored in both SQLite and files; changes require dual updates.

**Affected Areas**:
- Space metadata (SQLite `spaces` table + `space.md`)
- Run records (SQLite `runs` table + `.meridian/<space-id>/runs/<run-id>/` directory)
- Artifacts (SQLite `artifacts` table + actual files)

**Migration Strategy**:
1. Phase 1: Keep SQLite as read-only index for query speed
2. Phase 2: Migrate authority to files
3. Phase 3: Optional: Keep SQLite as optional secondary index

**Code Review Checklist**:
- [ ] All state mutations write to files first
- [ ] SQLite updates are derived from files (not the reverse)
- [ ] No bidirectional sync logic needed
- [ ] Read paths prioritize files over SQLite

---

### 2.2 Per-Space Skill Configuration

**Pattern**: Skills could vary per space (now removed, skills are agent-profile-owned).

**Files to Clean**:
- Remove any space metadata fields for skills
- Remove any logic selecting skills based on space properties
- Update prompt composition to ignore space-level skill config

**Affected**:
- `src/meridian/lib/domain.py` — check Space dataclass for skill fields
- Any space CRUD operations that read/write skill data

---

### 2.3 Space Summary Re-generation

**Pattern**: Summary regenerated from SQLite `spaces` table on every read.

**Files to Simplify**:

#### src/meridian/lib/space/summary.py
- **Function**: `generate_space_summary()` — simplify or remove
- Current approach: re-query SQLite, combine with files
- New approach: space.md is authority; cache summary in metadata

**Rollback Strategy**: Keep function but mark as deprecated; call it only for migrations.

---

## 3. Dependencies to Review for Removal

Check if these packages are only needed for SQLite-as-authority approach:

- [ ] `sqlite3` (stdlib, but reduce usage)
- [ ] `jsonschema` — if space validation moves to file schema
- [ ] Any ORM/migration tool (currently using hand-rolled migrations)

**Action**: After Phase 2, audit imports and remove unused dependencies from `pyproject.toml`.

---

## 4. Tests to Update/Remove

### 4.1 Tests Verifying SQLite Authority

**Files to Update**:

#### Tests verifying space creation in SQLite
- Search for tests calling `create_space()` directly
- Migrate to tests that verify file-based storage instead

#### Tests verifying skill composition
- `/home/jimyao/gitrepos/meridian-collab/meridian-channel/tests/test_cli_ux_fixes.py` — `--skills` flag tests
- `/home/jimyao/gitrepos/meridian-collab/meridian-channel/tests/test_flag_strategy.py` — `--skills` flag tests
- Any tests in `tests/test_space_*.py` that assume per-space skill config

#### Tests verifying space read/write
- `/home/jimyao/gitrepos/meridian-collab/meridian-channel/tests/test_space_slice6.py` — space read/write tests
- `/home/jimyao/gitrepos/meridian-collab/meridian-channel/tests/test_space_files_slice7.py` — space file listing tests
- These should be migrated to `meridian fs` command tests once fs commands are available

### 4.2 Update Patterns

```python
# Old test pattern (remove)
def test_space_read_writes_to_sqlite():
    space = adapter.create_space(SpaceCreateParams(...))
    assert space.id in sqlite_db  # Bad: tests SQLite authority

# New test pattern (add)
def test_space_metadata_persists_in_file():
    space = adapter.create_space(SpaceCreateParams(...))
    space_md = Path(f".meridian/{space.id}/space.md").read_text()
    assert space_md  # Good: tests file authority
```

---

## 5. Cleanup Checklist (Use During Implementation)

Use this checklist to track removal across phases:

### Phase 1: CLI Refactoring
- [ ] Remove `--skills` parameter from `run.py` (lines 52-59)
- [ ] Remove `skills=skill_flags` from `RunCreateInput()` (line 157)
- [ ] Remove `unknown_skills` error handler (lines 177-184)
- [ ] Remove `--skills` tests from `test_cli_ux_fixes.py`
- [ ] Remove `--skills` tests from `test_flag_strategy.py`
- [ ] Update `docs/cli-reference.md` to remove `--skills`
- [ ] Run `pnpm run lint` and fix any issues
- [ ] Verify `meridian run.create --help` no longer shows `--skills`

### Phase 2: Space Metadata Migration
- [ ] Verify space.md format in design review
- [ ] Refactor `get_space()` to read from `.meridian/<space-id>/space.md` first
- [ ] Refactor `create_space()` to write to `.meridian/<space-id>/space.md`
- [ ] Update `space_read_sync()` to use `meridian fs` equivalent
- [ ] Update `space_write_sync()` to use `meridian fs` equivalent
- [ ] Update `space_files_sync()` to use `meridian fs` equivalent
- [ ] Migrate space read/write tests to fs tests
- [ ] Keep SQLite `spaces` table as optional secondary index
- [ ] Add migration guide: "Migrate spaces from SQLite to files"

### Phase 3: JSON Index (Optional)
- [ ] Make SQLite `spaces` table read-only (add deprecation warnings)
- [ ] OR: Remove SQLite `spaces` table entirely if no query performance need
- [ ] Update schema version and add migration
- [ ] Update all SQLite adapters to read files instead

### Phase 4: Harness Integration
- [ ] Verify harness receives skills from agent profile (not CLI/space config)
- [ ] Update harness tests for file-based space metadata
- [ ] Verify space summary generation is correct

### Phase 5: Documentation
- [ ] Update ARCHITECTURE.md with file-based authority pattern
- [ ] Update BEHAVIORS.md to reflect new CLI (no `--skills`)
- [ ] Add migration guide for old spaces
- [ ] Update example workflows

### General Cleanup
- [ ] Run full test suite: `pytest tests/ -xvs`
- [ ] Run linter: `pnpm run lint` (if applicable to Python)
- [ ] Check for dead imports after removing features
- [ ] Update CHANGELOG.md with breaking changes
- [ ] Update gitignore for new `.meridian/` structure (if needed)

---

## 6. Backward Compatibility & Migration Path

### Space Migration Strategy

**For users upgrading from old version**:

```bash
# Script to migrate old SQLite spaces to new file-based format
meridian migrate spaces-v1-to-v2 [--force]
```

This script should:
1. Read all spaces from SQLite `spaces` table
2. Generate `.meridian/<space-id>/space.md` for each space
3. Copy space metadata from SQLite to YAML frontmatter
4. Mark old SQLite entries as migrated
5. Optionally backup old SQLite data

### Agent Profiles

**No changes needed**: Agent profiles are already file-based in `agent/<profile-name>.md`.

### Skills

**No changes needed**: Skills are already file-based in `skill/<skill-name>/` directory.

### Run Execution

**No breaking changes**: Run command semantics remain the same, just skills come from agent profile.

---

## 7. SQLite Deprecation Timeline

### Decision: Option A (Gradual Deprecation)

**Rationale**: Users get time to migrate; cleaner upgrade path.

**Timeline**:
- **v1.0**: Current state (SQLite as authority)
- **v1.1** (Phase 2): Space metadata authority moves to files; SQLite is read-only index
  - Deprecation warnings added when writing to old SQLite-only spaces
  - Migration command available: `meridian migrate spaces-v1-to-v2`
- **v2.0** (Next major): Remove SQLite `spaces` table entirely
  - Old SQLite-only spaces no longer supported
  - Clear migration guide in release notes

### Alternative: Option B (Clean Break)

**Rationale**: Simpler codebase; faster removal of tech debt.

**Timeline**:
- **v1.0**: Current state
- **v1.1** (Phase 2): Remove SQLite authority immediately
  - Breaking change: old spaces cannot be used without migration
  - Clear release notes with migration path
  - Pre-release warnings in documentation

**Recommendation**: Option A is better for production deployments; Option B is better for rapid iteration.

---

## 8. Files for Removal Decision (Per-Phase)

### Definitely Remove (No Decision Needed)
- `--skills` CLI flag (all references)
- `test_cli_ux_fixes.py` tests for `--skills`
- `test_flag_strategy.py` tests for `--skills`

### Probably Remove (Confirm in Design Review)
- `space_read_sync()` (replace with `meridian fs read`)
- `space_write_sync()` (replace with `meridian fs write`)
- `space_files_sync()` (replace with `meridian fs ls`)

### Review Before Removal (Clarify Design)
- `session_files.py` (decide on session file lifecycle)
- `summary.py` (decide on summary caching strategy)

### Keep as Index (Optional)
- SQLite `spaces` table (as secondary index for queries)
- SQLite `runs` table (already structured well)

---

## 9. File Path Quick Reference

For easy grep/removal:

```bash
# All --skills references
grep -r "\-\-skills" src/meridian/cli/ src/meridian/lib/ops/

# All space read/write
grep -r "space_read\|space_write\|space_files" src/meridian/

# All SQLite space operations
grep -r "create_space\|get_space" src/meridian/lib/adapters/sqlite.py

# All skill composition
grep -r "_render_skill_blocks\|compose_run_prompt" src/meridian/lib/prompt/

# All session file references
grep -r "session_files\|session_id" src/meridian/lib/space/

# All summary generation
grep -r "generate_space_summary" src/meridian/
```

---

## 10. Notes for Implementers

- **Don't over-cleanup**: Remove only what's in this document; don't refactor unrelated code.
- **Test each removal**: After removing a feature, run full test suite immediately.
- **Update CHANGELOG**: Document breaking changes clearly.
- **Ask before removing**: If a removal seems risky, ask in PR review before deleting.
- **Comments over removal**: If uncertain, leave code but add deprecation comment with removal timeline.

**Last Updated**: 2026-02-28
**Status**: Ready for use during Phase 1-3 implementation
