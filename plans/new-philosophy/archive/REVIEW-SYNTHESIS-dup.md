# Review Synthesis: Files-as-Authority Refactor Plan

**Date:** 2026-02-28
**Reviewers:** 4x gpt-5.3-codex + 1x claude-opus-4-6
**Session:** review-20260228T200207Z-307969

---

## Reviewer Focus Areas

| # | Model | Focus | Key Findings |
|---|-------|-------|-------------|
| 1 | codex | Implementation feasibility & task ordering | Over-serialized chain, MCP target wrong (server/main.py not cli/main.py), auto-create must cover MCP path |
| 2 | codex | Data model integrity & concurrency | space.json lost-update race, run-ID TOCTOU, JSONL recovery gap after SQLite removal, root .gitignore conflict |
| 3 | codex | CLI UX & MCP surface | MCP tool count mismatch (18 listed vs "19" claimed), current MCP has 26 tools, no run cancel |
| 4 | codex | Code reality check | Line numbers accurate, import graph gaps (2 test files import deleted modules), cli/main.py needs more cleanup |
| 5 | opus | Cross-examination | State machine 4→2 not tasked, supervisor rename unbounded, space.json authority ambiguous, run continue/retry not covered |

---

## CRITICAL Issues

### C1. State Machine Contradiction — 4 States → 2 Not Tasked
**Source:** Opus (C1)
**Evidence:** Plan Decision #18 says "two states: active, closed." Code has `Literal["active", "paused", "completed", "abandoned"]` in `domain.py:25`. `launch.py:490` transitions to `paused`/`abandoned`. Plan task t08 references `_transition_orphaned_space_states` which uses the 4-state machine.
**Impact:** If t01 creates `space_file.py` with 2-state enum but t08 still references `paused`/`abandoned`, tasks contradict each other.
**Decision needed:** Keep 2 states or 4?

### C2. `execvp` Replacement Not Explicitly in t08
**Source:** Opus (C3)
**Evidence:** The most important behavioral change (execvp → Popen+wait) is a plan decision and risk-table entry, but NOT an explicit bullet in t08. A codex agent implementing t08 might miss it.
**Fix:** Add explicit bullet to t08: "Replace `os.execvp` (TTY path, launch.py:418-452) with `subprocess.Popen` + `wait()` — required for session tracking and cleanup."

### C3. MCP Registration Lives in `server/main.py`, Not `cli/main.py`
**Source:** Codex #1, Opus
**Evidence:** Plan t14b targets `cli/main.py` for MCP filtering, but actual MCP tool registration is in `server/main.py`. Current MCP exposes 26 tools including `space_*`, `diag_repair`, `skills_reindex`.
**Fix:** t14b must target `server/main.py` for MCP filtering, not just `cli/main.py`.

### C4. Auto-Create Must Work in MCP Path Too
**Source:** Codex #1
**Evidence:** Plan t15 targets `cli/run.py` for auto-create logic. But `run_create` is also an MCP tool. If auto-create only lives in the CLI layer, MCP clients get no auto-create.
**Fix:** Auto-create logic must be in the operation layer (`lib/ops/run.py` or `lib/ops/_run_prepare.py`), not just CLI.

### C5. `space.json` Lost-Update Race — No Locking Specified
**Source:** Codex #2, Opus (G1)
**Evidence:** `space.json` is read-modify-write (pin file, update status, update last_activity). With multiple concurrent sessions, two agents could read, modify, and write simultaneously — last writer wins, losing the other's changes. Plan specifies flock for JSONL but NOT for space.json.
**Fix:** Specify per-space lock file (e.g., `space.lock`) for all space.json modifications. Use atomic write pattern (write to `.tmp` → `os.rename()`).

---

## HIGH Issues

### H1. `supervisor` Terminology — 30+ Occurrences Not Addressed
**Source:** Opus (C7)
**Evidence:** Plan Decision #8 says "no supervisor concept" but `launch_supervisor()`, `build_supervisor_prompt()`, `_resolve_supervisor_harness()`, `MERIDIAN_SUPERVISOR_COMMAND`, `config.supervisor.*` are all untouched by any plan task. Tests use `MERIDIAN_SUPERVISOR_COMMAND` as the harness override mechanism.
**Decision needed:** (a) Rename `supervisor` → something else across codebase, or (b) keep `supervisor` as internal nomenclature while external-facing concept is "primary agent."

### H2. Over-Serialized Chain — t09 and t11 Can Parallelize
**Source:** Codex #1
**Evidence:** t09 (run query/list/stats) doesn't depend on t07 (space domain) or t08 (space ops) code — it reads runs.jsonl independently. t11 (diag/context) doesn't depend on t10 (run execute). The chain t07→t08→t09→t10→t11 is artificially serial.
**Fix:** Allow t09 to start after t06 (not t08). Allow t11 to start after t06 (not t10). This parallelizes the consumer rewrite phase.

### H3. Root `.gitignore` May Block Nested Carve-Outs
**Source:** Codex #2
**Evidence:** If the repo root `.gitignore` contains `.meridian/`, then nested carve-outs in `.meridian/.gitignore` for `fs/` files are silently ignored by git. Codex #2 verified this empirically.
**Fix:** Ensure root `.gitignore` does NOT have `.meridian/`. The `.meridian/.gitignore` handles its own exclusions. Document this constraint.

### H4. Run Continue/Retry Not Covered by Plan Tasks
**Source:** Opus (X2)
**Evidence:** `cli-spec.md` lists `run continue` and `run retry` as agent-mode commands. These work through SQLite state. No plan task mentions rewriting them for JSONL.
**Fix:** Verify if `run continue`/`run retry` read from SQLite. If yes, add to t09 or t10.

### H5. `run_store.py` API Incomplete for Runtime Needs
**Source:** Codex #1
**Evidence:** Plan t02 specifies `start_run`, `finalize_run`, `list_runs`, `get_run`, `run_stats`, `space_spend_usd`. But current runtime also does `update_status` (run goes from `running` to `waiting` to `completed`). The JSONL model is append-only — status updates need a strategy (new event type? or query derives status from last event?).
**Fix:** Either (a) add event types for status transitions, or (b) document that run status is derived from the last event for that run ID (start=running, finalize=final state).

### H6. MCP Tool Count Mismatch
**Source:** Codex #3
**Evidence:** cli-spec.md MCP table lists 18 tool names but text says "Total: 19 MCP tools."
**Fix:** Recount and fix the number.

---

## MEDIUM Issues

### M1. Atomic Write for `space.json`
**Source:** Opus (G1)
**Evidence:** `space.json` is overwrite-in-place. A crash mid-write produces corrupt JSON. Unlike JSONL (append-only, naturally resilient), JSON overwrites lose the entire file.
**Fix:** t01 must use write-to-tmp + `os.rename()` pattern for `space.json`.

### M2. Run-ID TOCTOU — Lock Scope Must Cover Read + Append
**Source:** Codex #2, Opus (G2)
**Evidence:** `flock` for run ID must span from reading the count to appending the start event. If these are separate operations with the lock released between them, two agents get the same ID.
**Fix:** Document in t02/t03 that ID generation + event append must be one atomic operation under one flock hold.

### M3. Path Traversal in `fs` Commands
**Source:** Opus (G4)
**Evidence:** `fs write` takes a path argument. An agent passing `../../config.toml` could write outside `fs/`. No path validation is specified.
**Fix:** t14 must include path traversal validation: resolve path, verify it's under `fs/`, reject `..` components.

### M4. `space.write`/`space.read`/`space.files` Operation Registration Cleanup
**Source:** Opus (G5)
**Evidence:** `ops/space.py` (lines 516-626) registers `space.write`, `space.read`, `space.files` operations. Plan t14 creates `fs` replacements but doesn't mention removing old registrations.
**Fix:** Add to t14: "Remove `space.write`, `space.read`, `space.files` from `ops/space.py` operation registrations."

### M5. `space.json.status` Authority vs Flock Liveness
**Source:** Opus (C5)
**Evidence:** Is a space "active" because `space.json` says so, or because it has live session flocks? These can disagree. Current code derives space state from lock liveness.
**Fix:** Document authority chain: flock liveness is the ground truth, `space.json.status` is derived/cached, `doctor` reconciles.

### M6. Missing Test File Importers in Plan
**Source:** Codex #4
**Evidence:** `tests/test_config_slice2.py` imports `meridian.lib.state.db`, `tests/test_config_s4b_env_overrides.py` imports `meridian.lib.adapters.sqlite`. Plan doesn't mention these.
**Fix:** Add these test files to t12 or t16 modify lists.

### M7. `cli/main.py` Import Cleanup Incomplete
**Source:** Codex #4
**Evidence:** Plan cites removal at lines 320 and 409, but imports at lines 19-20 and command group wiring at 200-201 also need cleanup.
**Fix:** Add full import/wiring cleanup to t13.

### M8. NFS/Docker flock Portability
**Source:** Codex #2
**Evidence:** `flock` is advisory-only and doesn't work reliably on NFS. Docker containers may have different lock semantics.
**Fix:** Document as a known limitation in architecture.md. For MVP, local filesystem is the supported target.

---

## LOW Issues

### L1. Line Number References Will Drift
**Source:** Opus (C4), Codex #4
**Evidence:** Plan references specific line numbers (e.g., `:266-279`, `:372-383`). These are already slightly off and will drift further as Group A modifies adjacent code.
**Recommendation:** Use function names instead of line numbers in task descriptions.

### L2. `list` Shortcut in cli-spec Help Example
**Source:** Opus (X1)
**Evidence:** cli-spec.md human-mode help output shows `list → space list` as a shortcut, but the shortcuts section says only `start` is kept.
**Fix:** Remove `list` from the example help output.

### L3. Agent Can't See Own Space Status
**Source:** Opus (X3)
**Evidence:** `space show` is human-mode only. Agents can't check their own space name, status, or description. `context list` shows pinned files but not other space metadata.
**Decision needed:** Add `space show` to agent mode, or enrich `context list` to include space metadata.

### L4. `doctor` — Diagnose vs Repair
**Source:** Opus (D3)
**Evidence:** Current code separates `diag doctor` (check) and `diag repair` (fix). Plan merges to just `doctor` but doesn't clarify if it auto-repairs or needs a flag.
**Decision needed:** Does `doctor` auto-repair, or does it need `--repair`/`--fix`?

### L5. Scalability Bound Undocumented
**Source:** Opus (D1)
**Evidence:** At 100k runs, JSONL parse could be 40MB+ and 100ms+. No documented bound.
**Recommendation:** Add to Non-Goals: "At >10k runs per space, consider SQLite index layer."

### L6. Merge Conflict Risk for Parallel Tasks
**Source:** Opus
**Evidence:** t01-t05 run in parallel. Multiple agents may need to modify `domain.py` (e.g., `Space` dataclass changes for `space.json` format).
**Recommendation:** Add to risk table. Mitigation: lock `domain.py` changes to a single pre-task or assign one agent as domain types owner.

### L7. `sessions.jsonl` May Be Over-Design
**Source:** Opus (D4)
**Evidence:** Existing code uses only lock files for session tracking (`cleanup_orphaned_locks()`). The new plan adds `sessions.jsonl` on top of locks. Is the JSONL needed if flock-based liveness is already sufficient?
**Decision needed:** Keep `sessions.jsonl` for audit trail, or rely solely on flock?

---

## Decisions Needed Before Implementation

| # | Issue | Options |
|---|-------|---------|
| 1 | State machine: 2 states or 4? | (a) Keep 2 (active/closed) — add explicit migration task (b) Keep 4 |
| 2 | `supervisor` terminology | (a) Rename throughout (add task) (b) Keep as internal name |
| 3 | Agent seeing space status | (a) Add `space show` to agent mode (b) Enrich `context list` |
| 4 | `doctor` behavior | (a) Auto-repair (b) Check only, `--fix` for repair |
| 5 | `sessions.jsonl` necessity | (a) Keep for audit (b) Drop, use flocks only |

## Fixes That Can Be Applied Now (No Decisions Needed)

1. Add explicit execvp→Popen bullet to t08
2. Retarget t14b MCP filtering to `server/main.py`
3. Move auto-create logic to operation layer (not just CLI)
4. Add space.json locking + atomic write to t01 spec
5. Add run-ID lock scope clarification to t02/t03
6. Add path traversal validation to t14
7. Add operation registration cleanup to t14
8. Add test file importers to t12/t16
9. Add cli/main.py full import cleanup to t13
10. Fix MCP tool count in cli-spec.md
11. Remove `list` shortcut from cli-spec help example
12. Verify run continue/retry need rewriting
13. Document root .gitignore constraint
14. Use function names instead of line numbers in tasks
15. Document flock NFS limitation
16. Add scalability bound to Non-Goals
17. Add merge conflict risk to risk table
