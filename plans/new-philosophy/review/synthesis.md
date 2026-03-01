# Plan Review Synthesis: Multi-Model Cross-Examination

**Date**: 2026-02-28
**Reviewers**: 3x gpt-5.3-codex (architecture critic, deletion auditor, contrarian) + 1x claude-opus-4-6 (code-grounded synthesis)
**Subject**: All plan files in `plans/new-philosophy/`
**Method**: Each model read plan docs AND cross-checked against actual source code with line references

---

## Executive Summary

**The philosophy is sound. The implementation plan is 3-5x over-scoped.**

All 4 reviewers converge on:
1. The codebase is **60-80% aligned** with the new philosophy already
2. The 5-phase, 10-15 week plan is **inflated** — real work is 3-4 weeks
3. The `meridian fs` 8-command group **contradicts** the stated philosophy
4. SQLite is **deeply coupled** beyond what the plans acknowledge (direct SQL in ops/space layers, `OperationRuntime` hard-wired to concrete stores)
5. The prompt/skill composition system is **essential** — keep it, just change skill source to agent profiles
6. Runs stay in SQLite; only space metadata migrates to files

---

## Consensus Findings

### 1. Plans Over-Scope the Work

| Plan Says | Reality (verified by Codex) |
|-----------|-----------------------------|
| Agent profiles need work | Already file-based, working correctly (IMPLEMENTATION-GAPS.md:57) |
| Skills need work | Already file-based, loaded from profiles (IMPLEMENTATION-GAPS.md:70) |
| Sessions need work | Already file-based, working correctly (IMPLEMENTATION-GAPS.md:83) |
| Harness adapters need work | Already implemented for Claude/Codex/OpenCode (IMPLEMENTATION-GAPS.md:243) |
| 5 phases, 10-15 weeks | 3-4 weeks of actual work |

**Codex #1 (Architecture Critic)**: "The 8-10 week number is inflated by broad fs work + heavy docs phase."
**Codex #3 (Contrarian)**: Ran `uv run pytest --collect-only` and found 247 tests, with ~118 in the impacted superset — significant but manageable.

### 2. `meridian fs` Contradicts Philosophy

The philosophy says: *"Meridian is NOT a file system."*
The plan proposes 8 filesystem commands: `ls, cat, read, write, cp, mv, rm, mkdir`.

**All 4 reviewers flagged this contradiction.**

- **Codex #1**: "The plan turns Meridian into a mini shell even though it's meant to be a coordination layer" (IMPLEMENTATION-PLAN.md:107, ARCHITECTURE.md:30)
- **Codex #2**: Current `space read/write/files` are session-scoped coordination files, not generic filesystem control (cli/space.py:190, ops/space.py:582)
- **Codex #3**: "A small shim is useful; an 8-command filesystem layer is not. Cut Phase 1 tasks for `cat/cp/mv/rm/mkdir`."

**Resolution (user decision)**:
- Expose `MERIDIAN_SPACE_FS` env var for agents with shell access (primary path)
- Keep `fs read/write/ls` (renamed from `space read/write/files`) as MCP-accessible surface — since every CLI command is also exposed as an MCP tool, and MCP clients can't shell out
- Don't build `cat/cp/mv/rm/mkdir` — add via MCP when need is proven

### 3. SQLite Is Deeply Coupled

**Codex #2 (Deletion Auditor)** did a comprehensive module-by-module audit:

| Layer | SQLite Coupling Found |
|-------|----------------------|
| `ops/_runtime.py` | Hard-couples to `SQLiteRunStore`, `SQLiteSpaceStore`, `SQLiteContextStore` |
| `ops/run.py`, `_run_query.py`, `_run_execute.py` | Direct SQLite queries for listing/stats/show/budget rollup |
| `ops/space.py` | Direct SQLite reads in `space_show_sync` |
| `ops/diag.py` | Assumes SQLite authority; repairs `runs.jsonl` compatibility artifact |
| `state/db.py` | Centralizes SQLite connection as default state path |
| `state/schema.py` | Spaces/runs/pinned_files/workflow authored in DB schema |
| `state/id_gen.py` | Counters stored in DB (`schema_info`, `spaces.run_counter`) |
| `state/jsonl.py` | Legacy dual-write/import compatibility path |
| `space/crud.py` | Direct SQL for space CRUD |
| `space/summary.py` | Updates DB `summary_path` |

**Opus finding**: `runtime.space_store` and `runtime.context_store` on `OperationRuntime` are **dead code** — only `run_store` is actually used (2 callsites). These should be removed, not abstracted.

**Prerequisite**: Consolidate all raw SQL behind `StateDB` interfaces BEFORE migrating authority to files.

### 4. Prompt Composition Is Essential (Don't Remove)

**Codex #1** traced the full pipeline:
- CLI flag input (`run.py:55`)
- Defaults merge with profile skills (`assembly.py:52`)
- Prompt assembly (`compose.py:50`)
- Run prepare wiring (`_run_prepare.py:261`)

**Resolution**: Remove/soft-deprecate CLI `--skills` for normal use, but do NOT remove composition pipeline. Change skill source-of-truth to agent profiles.

### 5. Harness-Agnostic Is Aspirational, Not Real

**Codex #3 (Contrarian)** challenged this directly:
- "Everything works everywhere" claim (MVP-SCOPE.md:12) **conflicts** with blockers marked not-implemented (CODEX-BLOCKERS.md:24, :59, :92)
- CODEX-BLOCKERS.md shows `Last Updated: 2025-02-28` — stale for 2026 planning
- `launch.py` hardcodes `claude` executable path (Codex #2 confirmed)

**Resolution**: Replace binary "supported" claims with capability-tiered matrix per harness (`native`, `degraded`, `manual`). Fail-fast warnings when running degraded.

---

## DELETE / REFACTOR / KEEP Matrix (from Codex #2 Deletion Auditor)

### DELETE

| File | Reason |
|------|--------|
| `lib/ops/migrate.py` | Legacy import path (runs.jsonl, workspace-era) — no backwards compatibility needed |
| `cli/migrate.py` | CLI surface for above |
| `lib/state/jsonl.py` | Compatibility layer only — unnecessary in file-authoritative design |
| `lib/space/session_files.py` | Session-scoped flat store conflicts with new `fs` model |
| `cli/export.py` | Export workaround for DB-driven artifact discovery — unnecessary once files are authoritative |

### REFACTOR

| File | Change Needed |
|------|---------------|
| `lib/ops/_runtime.py` | Remove dead `space_store`/`context_store` fields; protocol interfaces for `RunStore` |
| `lib/ops/space.py` | Remove `space.write/read/files`; route to new `fs.*` ops; stop direct SQLite reads |
| `lib/ops/run.py` | Enforce required space context; move queries behind index abstraction |
| `lib/ops/_run_query.py` | Replace direct SQLite row reads with index abstraction |
| `lib/ops/_run_execute.py` | Replace `_space_spend_usd` DB queries with index-provider call |
| `lib/ops/diag.py` | Shift diagnostics to filesystem authority checks; drop `runs_jsonl` rebuild |
| `lib/state/db.py` | Reposition as optional index backend, not core authority |
| `lib/state/schema.py` | Minimize to optional index needs; remove legacy migration branches |
| `lib/state/id_gen.py` | Generate IDs from filesystem (not DB counters) |
| `lib/space/crud.py` | Rewrite create/get/list/transition on `space.md` file model |
| `lib/space/context.py` | Persist pinned files in `space.md` frontmatter, not DB table |
| `lib/space/summary.py` | Merge with canonical `space.md` generation; stop updating DB `summary_path` |
| `lib/space/launch.py` | Remove Claude-only harness restriction; standardize env vars |
| `lib/prompt/reference.py` | Remove `@name` session reference tied to `MERIDIAN_SESSION`; use `fs/` paths |
| `cli/space.py` | Keep lifecycle only (start/resume/list/show/close); remove session file commands |
| `cli/run.py` | Enforce explicit space requirement for create/continue/retry |
| `cli/main.py` | Register `fs` group; remove `migrate`/`export` if deleted |

### KEEP (No Changes Needed)

- `lib/ops/registry.py` — Clean operation registry
- `lib/ops/codec.py` — Generic schema/coercion
- `lib/ops/models.py` — Harness/model catalog
- `lib/ops/skills.py` — File-based skill registry
- `lib/ops/config.py` — File-based config surface
- `lib/state/artifact_store.py` — Artifact handling
- `cli/config_cmd.py`, `cli/models_cmd.py`, `cli/skills_cmd.py` — Working correctly
- `cli/output.py`, `cli/format_helpers.py` — UI utilities

---

## What's Missing from Plans (All Reviewers)

### Codex-identified gaps:
1. **Concurrency contract** — Atomic writes, lock granularity, conflict behavior for file authority (Codex #1)
2. **Agent communication model** — Mailbox/events/protocol beyond shared `fs/` (Codex #1)
3. **Context compaction lifecycle** — Rehydration rules across resume (Codex #1)
4. **Crash consistency** — Dual-write transition recovery (Codex #1)
5. **Test rewriting budget** — ~118 tests impacted; needs dedicated budget, not afterthought (Codex #3)
6. **Prompt/reference as first-class workstream** — Core control-plane logic treated as peripheral in plans (Codex #3)
7. **Stale blockers doc** — CODEX-BLOCKERS.md dated 2025, needs re-validation (Codex #3)

### Opus-identified gaps (things Codex missed):
8. **`OperationRuntime` dead code** — `space_store` and `context_store` fields never used; `run_store` used at only 2 callsites
9. **`os.execvp` launch pattern** — Process replacement at `launch.py:436` means no cleanup runs; spaces stuck `active` forever if supervisor crashes
10. **Duplicated transition logic** — `_ALLOWED_SPACE_TRANSITIONS` defined in BOTH `space/crud.py:12-17` AND `adapters/sqlite.py:52-61` (SRP violation)
11. **JSONL dual-write is already a third format** — `StateDB.__init__` has `jsonl_dual_write: bool = True`; adding JSON index would be a 4th storage path. JSONL is write-only (never read for business logic) — consider removing entirely
12. **`skill_registry.py` has its own SQLite DB** — Separate from `StateDB`, not mentioned in plans, would survive any StateDB refactor unchanged
13. **`supports_native_skills` capability flag** — Declared by all harnesses but **never checked** at runtime; skills always prompt-injected regardless
14. **MCP server surface** — `server/` directory exposes operations via FastMCP; operation renames must propagate to MCP tool names
15. **40 raw SQL callsites** (Opus precise count) across 10 files: `ops/space.py:372-384`, `space/crud.py:41-58`, `ops/run.py:234,292`, `ops/_run_query.py:30,88`, `ops/_run_execute.py:151`, `space/summary.py:27,112,144`, `space/launch.py:436`, `ops/diag.py:82,258`

---

## Revised Implementation Plan

### Phase 1: Seal SQLite Abstraction (3-5 days)
**Goal**: Consolidate all raw SQL into StateDB. Zero behavior change.

- Remove dead `space_store`/`context_store` from `OperationRuntime`
- Move direct SQL in ops/space layers into `StateDB` methods
- Define `Protocol` interfaces for `RunStore` (keep SQLite impl)
- Remove `lib/state/jsonl.py` (legacy compatibility)
- Remove `lib/ops/migrate.py` + `cli/migrate.py`
- All 247 tests continue passing unchanged

**Risk**: Low (pure refactoring + dead code removal)

### Phase 2: Space Metadata to Files (5-8 days)
**Goal**: `.meridian/<space-id>/space.md` becomes authority for space metadata.

- Implement `space.md` with YAML frontmatter as authority (create on `space start`)
- Read from `space.md` for `space show/list/resume`
- Persist pinned files in `space.md` frontmatter (not DB table)
- Keep SQLite as derived index (rebuilt from filesystem)
- Add `meridian diag rebuild-index` for reconciliation
- Re-root session files from `.meridian/sessions/` to `.meridian/<space-id>/fs/`
- Rename `space write/read/files` → `fs write/read/ls`
- Update ID generation (filesystem-derived counters)
- Update `lib/prompt/reference.py` for new `fs/` paths
- **30-50 tests need updating** (Codex #3 estimates higher at ~75 in broader subset)

**Risk**: Medium (core data path change + concurrency concerns)

### Phase 3: Cleanup & Harness Polish (3-5 days)
**Goal**: Remove deprecated code, make harness launching generic.

- Remove `--skills` as runtime default (keep as optional override from profile)
- Update `launch.py` to not hardcode Claude as supervisor harness
- Add `MERIDIAN_SPACE_ID` enforcement on run creation
- Remove `cli/export.py` + `lib/space/session_files.py`
- Clean up workspace → space rename remnants
- Add capability-tier matrix per harness with fail-fast warnings
- Update CLAUDE.md, README.md with final state

**Risk**: Low

### Total: ~14-18 working days (3-4 weeks)

---

## What to DELETE from Current Plans

| Plan File | What to Cut | Why |
|-----------|-------------|-----|
| IMPLEMENTATION-PLAN.md | Phase 0 (Validation) | Done. This review IS the validation. |
| IMPLEMENTATION-PLAN.md | Phase 1 Tasks 1.3-1.5 (`fs cat/cp/mv/rm/mkdir`) | Contradicts philosophy. Agents use native tools. |
| IMPLEMENTATION-PLAN.md | Phase 3 (JSON Index as full phase) | Format churn unless paired with SQLite removal. Fold into Phase 2 subtask. |
| IMPLEMENTATION-PLAN.md | Phase 4 Tasks 4.2-4.3 (Codex/OpenCode E2E) | Premature. Harnesses have documented blockers. Test Claude first. |
| IMPLEMENTATION-PLAN.md | Phase 5 (Documentation as full phase) | Docs should happen alongside implementation, not after. |
| CODEX-BLOCKERS.md | Feature request templates | Premature. File issues when we actually test. |
| CODEX-BLOCKERS.md | Stale 2025 dates | Re-validate before relying on blocker claims. |
| MVP-SCOPE.md | 13-week timeline | Replace with 3-4 week timeline. |
| MERIDIAN-CHANNEL.md | Entire file (1305 lines) | Mega-document duplicates all other files. Archive it. |

## What to KEEP

| Plan File | What's Good |
|-----------|-------------|
| ARCHITECTURE.md | Target directory structure, space.md format, data flow — update with Phase 1 prerequisite |
| BEHAVIORS.md | Command syntax and examples for space lifecycle |
| IMPLEMENTATION-GAPS.md | Component analysis table — update priorities |
| MVP-SCOPE.md | Claude-first strategy, harness feature matrix |

## What to ADD

1. **SQLite Consolidation Phase** — The missing prerequisite (seal the abstraction before swapping it)
2. **Concurrency & Crash Recovery Spec** — How file authority handles multi-agent writes and failures
3. **ID Generation Strategy** — Filesystem-derived IDs to replace SQLite counters
4. **Test Budget** — Dedicated stream, not afterthought (~118 tests impacted)
5. **Harness Capability Tiers** — Replace binary "supported" with `native/degraded/manual` per feature

---

## Decision Points for User

1. ~~**`meridian fs` scope**~~: **DECIDED** — `MERIDIAN_SPACE_FS` env var + keep 3 commands (`fs read/write/ls`) for MCP surface. No new commands.
2. ~~**Runs storage**~~: **DECIDED** — Runs to `.meridian/<space-id>/runs.jsonl` (already half-built). No SQLite.
3. ~~**SQLite deprecation**~~: **DECIDED** — Remove entirely. Files are authority, scale doesn't justify a DB. Drop `state/db.py`, `state/schema.py`, `adapters/sqlite.py`, all migration logic.
4. ~~**Phase ordering**~~: **DECIDED** — Single phase: build file authority + rip out SQLite + CLI cleanup. Start immediately.
5. ~~**Dead code**~~: **DECIDED** — All in one phase (rip the bandaid): `state/db.py`, `state/schema.py`, `adapters/sqlite.py`, `state/jsonl.py` dual-write, `state/id_gen.py` (rewrite), `ops/migrate.py`, `cli/migrate.py`, `cli/export.py`, `ops/diag.py` rebuild logic.

---

## Run References

| Run ID | Model | Role | Report |
|--------|-------|------|--------|
| `20260228T163001Z__...246158` | gpt-5.3-codex | Architecture Critic | KEEP/CUT/RETHINK/ADD with line refs |
| `20260228T163615Z__...252408` | gpt-5.3-codex | Deletion Auditor v2 | DELETE/REFACTOR/KEEP matrix |
| `20260228T163044Z__...247952` | gpt-5.3-codex | Contrarian | 7-point challenge assessment |
| `20260228T163552Z__...252119` | claude-opus-4-6 | Code-Grounded Synthesis | Full synthesis with grades, risks, execution plan |

---

---

## Top 5 Risks (Opus Assessment)

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **SQLite sealing breaks tests** — 59 tests use raw SQL for verification; changing them while changing underlying code is dangerous | High | Seal abstraction first, keep old test assertions as secondary verification |
| 2 | **`os.execvp` makes crash recovery impossible** — process replaced, no Python cleanup runs | High | Write `space.md` with `state: active` before `execvp`; add `meridian diag repair` for orphaned spaces |
| 3 | **Concurrent `sqlite3.connect()` from multiple agents** — supervisor and child agents may write simultaneously | Medium | Direct `connect()` calls bypass centralized timeout settings; must consolidate |
| 4 | **Run ID generation after SQLite deprecation** — monotonic counters require SQLite | Medium | Keep SQLite for counters + run tracking; only deprecate for space metadata |
| 5 | **JSONL dual-write maintenance burden** — every StateDB change updates both SQLite and JSONL, but JSONL is never read | Low | Remove JSONL entirely or declare it audit-only |

---

## Opus Final Verdict

> The prompt/skill composition pipeline is **sacred** — it is the core value of the coordination layer. Don't touch it except to make `--skills` additive over agent profile defaults (which is already how it works).
>
> The plans are **directionally correct** but **over-scoped by ~3x** and **misordered**. The critical path is:
> 1. Seal the SQLite abstraction (40 bypass callsites → 0)
> 2. Make `space.md` the authority (0 references today → full lifecycle)
> 3. Minimal CLI rename (`read/write/files` → `fs read/write/ls`)

---

**This review was produced by cross-examining 3 gpt-5.3-codex reviewers + 1 claude-opus-4-6 reviewer against the actual codebase. Each reviewer read 15-30 source files and produced code-grounded findings with line references. Full run reports available in `.orchestrate/runs/agent-runs/`.**
