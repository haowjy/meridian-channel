# Meridian-Channel Implementation Gaps

**Status:** Approved

This document compares current implementation against target architecture, identifying what needs to change and why.

## Component-by-Component Gap Analysis

### 1. Space Metadata

| Aspect | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| **Location** | SQLite `spaces` table | `.meridian/<space-id>/space.md` | File-based authority | High |
| **Index** | SQLite (authority) | JSON `index/spaces.json` (cache) | Index de-authorization | High |
| **Pinned Files** | SQLite | `space.md` YAML list | File-based | Medium |
| **Naming** | `space_id` (UUID-like) | Human-readable slugs + IDs | UX improvement | Low |

**Changes Needed:**

1. **Create space.md Format**
   - Markdown file per space with metadata
   - Include: ID, name, created_at, state, pinned_files
   - Version in TOML frontmatter for schema evolution

2. **Migrate Space Data**
   - Export all rows from SQLite `spaces` table
   - Generate `.meridian/<space-id>/space.md` for each
   - Keep SQLite in sync as optional index

3. **Refactor Space CRUD**
   - Update `lib/space/crud.py` to read/write files
   - Keep SQLite writes for backward compatibility
   - Make file reads authoritative

4. **Update Operations Layer**
   - `lib/ops/space.py` → read space metadata from files
   - Fall back to SQLite if file missing (migration period)

**Affected Files:**
- `src/meridian/lib/space/crud.py` (CRUD logic)
- `src/meridian/lib/adapters/sqlite.py` (optional index writes)
- `src/meridian/lib/adapters/filesystem.py` (new file I/O)
- `src/meridian/lib/ops/space.py` (metadata source selection)

**Estimated Effort:** Large (requires careful migration)

**Risk:** Medium (data loss if migration fails, but recoverable from SQLite)

**Complexity:** File parsing, schema changes, backward compatibility

---

### 2. Agent Profiles

| Aspect | Current | Target | Status |
|--------|---------|--------|--------|
| **Location** | `.meridian/agents/*.md` | `.meridian/<space-id>/agents/*.md` | ✅ Already correct |
| **Format** | Markdown | Markdown | ✅ Already correct |
| **Scope** | Global | Per-space | ✅ Already correct |
| **Registration** | File-based | File-based | ✅ Already correct |

**Status:** ✅ No changes needed. Agent profiles are already file-based and working correctly.

---

### 3. Skills

| Aspect | Current | Target | Status |
|--------|---------|--------|--------|
| **Location** | `.meridian/skills/*.md` | `.meridian/<space-id>/skills/*.md` | ✅ Already correct |
| **Format** | Markdown templates | Markdown templates | ✅ Already correct |
| **Scope** | Global (optional index) | Per-space | ✅ Already correct |
| **Registration** | File-based | File-based | ✅ Already correct |

**Status:** ✅ No changes needed. Skills are already file-based and working correctly.

---

### 4. Sessions

| Aspect | Current | Target | Status |
|--------|---------|--------|--------|
| **Location** | `.meridian/sessions/<session-id>/` | `.meridian/sessions/<session-id>/` | ✅ Correct |
| **Persistence** | Ephemeral | Ephemeral | ✅ Correct |
| **Format** | JSON metadata + logs | JSON metadata + logs | ✅ Correct |
| **Locks** | File-based locks | File-based locks | ✅ Correct |

**Status:** ✅ No changes needed. Session management is already working correctly.

---

### 5. Filesystem Commands

| Command | Current | Target | Gap | Priority |
|---------|---------|--------|-----|----------|
| `read` | `meridian space read` | `meridian fs read` | Rename group | High |
| `write` | `meridian space write` | `meridian fs write` | Rename group | High |
| `ls` | Missing | `meridian fs ls` | New command | High |
| `cat` | Missing | `meridian fs cat` | New command | High |
| `cp` | Missing | `meridian fs cp` | New command | Medium |
| `mv` | Missing | `meridian fs mv` | New command | Medium |
| `rm` | Missing | `meridian fs rm` | New command | Medium |
| `mkdir` | Missing | `meridian fs mkdir` | New command | Medium |

**Changes Needed:**

1. **Create `meridian fs` Command Group**
   - New file: `src/meridian/cli/filesystem.py`
   - Implement all 8 commands listed above
   - Use existing space context (`MERIDIAN_SPACE_ID`)

2. **Implement Filesystem Operations**
   - Create `lib/ops/filesystem.py` with operation specs
   - Reuse existing `lib/adapters/filesystem.py` I/O
   - Add path validation (no traversal outside space)

3. **Update CLI Registration**
   - Register in `main.py` under app
   - Rename old `space read/write` commands (or deprecate)

4. **Add Path Validation**
   - Prevent `../../etc/passwd` type attacks
   - Reject absolute paths outside space
   - Clear error messages

**Affected Files:**
- `src/meridian/cli/filesystem.py` (NEW)
- `src/meridian/lib/ops/filesystem.py` (NEW)
- `src/meridian/cli/main.py` (registration)
- `src/meridian/lib/adapters/filesystem.py` (enhanced I/O)

**Estimated Effort:** Medium (straightforward CLI + ops)

**Risk:** Low (non-destructive additions)

**Complexity:** Path validation, recursion flags, output formatting

---

### 6. Run Execution

| Aspect | Current | Target | Status |
|--------|---------|--------|--------|
| **MERIDIAN_SPACE_ID required** | ✅ Yes | ✅ Yes | ✅ Correct |
| **Error on missing** | ✅ Error message | ✅ Clear error | ⚠️ Verify message |
| **No auto-create** | ✅ No | ✅ No | ✅ Correct |
| **Harness detection** | ✅ Implemented | ✅ Implemented | ✅ Correct |

**Status:** ✅ Mostly correct. Just need to verify error messages are clear.

**Verification needed:**
- Check error message when `MERIDIAN_SPACE_ID` not set
- Ensure it suggests `meridian space start` and `meridian space resume`
- Make sure it doesn't try to auto-create spaces

**Affected Files:**
- `src/meridian/lib/ops/run.py` (error handling)
- `src/meridian/cli/run.py` (error messaging)

**Estimated Effort:** Small (message refinement only)

**Risk:** Low

---

### 7. Index (JSON vs SQLite)

| Aspect | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| **Format** | SQLite | JSON files | Format simplification | Medium |
| **Regenerability** | Requires migration | From files | Improvement | Medium |
| **Scope** | Single DB | Per-index files | Modularity | Low |

**Current State:**
SQLite is used for:
- Space listings (fast queries)
- Run history (aggregation)
- Search indexes

**Proposed Change:**
Create JSON index files that are:
- Generated from markdown sources
- Cached for performance
- Regenerated on changes
- Simpler than SQL migrations

**Candidate JSON Files:**
```
.meridian/index/
├── spaces.json          # List of all spaces with metadata
├── run-stats.json       # Aggregated run statistics
└── [space-id].json      # Per-space run index
```

**Format Example (spaces.json):**
```json
{
  "generated_at": "2025-02-28T12:00:00Z",
  "spaces": [
    {
      "id": "w145",
      "name": "novel-draft-v2",
      "state": "active",
      "created_at": "2025-02-28T10:30:00Z",
      "last_activity": "2025-02-28T12:15:00Z",
      "primary_agent": "alice"
    }
  ]
}
```

**Changes Needed:**

1. **Create JSON Index Generator**
   - Scan `.meridian/spaces/*/space.md`
   - Generate `index/spaces.json`
   - Run on space changes

2. **Update List Operations**
   - Read from `index/spaces.json` instead of SQLite
   - Fall back to regenerate if missing

3. **Keep SQLite Optional**
   - Don't remove SQLite entirely (backward compatibility)
   - Let users opt-in to JSON index
   - Can eventually deprecate SQLite

**Affected Files:**
- `src/meridian/lib/adapters/index.py` (NEW)
- `src/meridian/lib/ops/space.py` (use new index)
- `src/meridian/lib/space/summary.py` (index generation)

**Estimated Effort:** Medium (JSON generation + format decisions)

**Risk:** Low (non-authoritative cache)

---

### 8. Harness Integration

| Aspect | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| **Claude adapter** | ✅ Implemented | ✅ Implemented | None | - |
| **Codex adapter** | ✅ Implemented | ✅ Implemented | None | - |
| **OpenCode adapter** | ✅ Implemented | ✅ Implemented | None | - |
| **Env var passing** | ✅ Set | ✅ Set | None | - |
| **Session hooks** | ⚠️ Partial | ✅ Full lifecycle | Missing | Medium |
| **Error translation** | ⚠️ Inconsistent | ✅ Unified | Standardize | Medium |

**What's Working:**
- Harness detection (Claude/Codex/OpenCode)
- Environment variable passing
- Basic command execution
- Output streaming

**What's Missing:**

1. **Session Lifecycle Hooks**
   - No callback when agent spawns
   - No callback when agent completes
   - No callback on errors
   - Needed for tracking, logging, state updates

2. **Unified Error Messages**
   - Each harness has different error format
   - Should translate to consistent messages
   - Example: "CUDA out of memory" → "Harness overloaded, try again"

3. **Automatic Retry Logic**
   - Transient harness failures not retried
   - Should have exponential backoff
   - Should track retries in run metadata

**Changes Needed:**

1. **Define Hook Protocol**
   - Agent spawn hook
   - Agent complete hook
   - Agent error hook
   - Progress update hook

2. **Implement Hook System**
   - Create `lib/harness/hooks.py`
   - Each adapter fires events
   - Central registry for subscribers

3. **Standardize Error Messages**
   - Map harness-specific errors to categories
   - Include recovery suggestions
   - Log full error for debugging

4. **Add Retry Logic**
   - Exponential backoff (1s, 2s, 4s, 8s)
   - Configurable max retries
   - Transient vs permanent error detection

**Affected Files:**
- `src/meridian/lib/harness/adapter.py` (hook invocation)
- `src/meridian/lib/harness/hooks.py` (NEW)
- `src/meridian/lib/ops/run.py` (retry logic)
- `src/meridian/lib/harness/{claude,codex,opencode}.py` (error normalization)

**Estimated Effort:** Large (requires careful error categorization)

**Risk:** Medium (hook system must be reliable)

**Complexity:** Error classification, async event handling, retry state management

---

## Summary Table

| Component | Current → Target | Effort | Risk | Priority |
|-----------|------------------|--------|------|----------|
| Space Metadata | SQLite → Files | Large | Medium | High |
| Agent Profiles | Files → Files | None | None | - |
| Skills | Files → Files | None | None | - |
| Sessions | Files → Files | None | None | - |
| Filesystem Cmds | Missing → `meridian fs` | Medium | Low | High |
| Run Execution | OK → Verify | Small | Low | Low |
| Index | SQLite → JSON | Medium | Low | Medium |
| Harness Integration | Partial → Full | Large | Medium | Medium |

## Migration Strategy

**Phase 1 (High Priority):**
1. Space Metadata migration (enables git-friendly storage)
2. Filesystem commands (enables agent coordination)

**Phase 2 (Medium Priority):**
3. JSON index (improves performance without breaking changes)
4. Harness hooks (improves reliability)

**Phase 3 (Low Priority):**
5. Error message standardization
6. Retry logic

**Backward Compatibility:**
- Keep SQLite reads during Phase 1 (fall back if `.md` missing)
- Deprecate `space read/write` after Phase 1 (don't remove)
- No schema migrations needed (file-based)
- Can run old and new code side-by-side
