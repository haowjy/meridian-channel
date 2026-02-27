# Post-Sandbox Cleanup & Refactoring

**Status:** done (all 8 tasks complete)

## Context

After implementing the 13-slice sandbox compatibility plan, three independent reviews (2 codex, 1 opus-timeout + codex-retry) identified cleanup opportunities and residual bugs. This plan consolidates findings into actionable tasks.

## Sources

- Plan verification review (codex): `20260227T010316Z__reviewer__gpt-5.3-codex__645869`
- Code quality review (codex): `20260227T011912Z__reviewer__gpt-5.3-codex__670850`
- Dead code audit (codex): `20260227T010337Z__reviewer__gpt-5.3-codex__647160`

---

## Task 1: Fix `.git` directory boundary escape (Bug 2 regression)

**Priority:** P0 — correctness bug
**File:** `src/meridian/lib/config/_paths.py:38`

`resolve_repo_root()` only checks `git_marker.is_file()` for worktree/submodule `.git` files. Normal repos have `.git/` as a **directory**, which is not caught. This means the boundary-escape bug (Bug 2) is only partially fixed — it works for submodules but not for standalone repos nested under a parent with `.agents/skills`.

**Fix:** Change boundary check to `git_marker.exists()` (catches both file and directory). Add test for `.git` directory case.

---

## Task 2: Sanitize workspace launch environment (Bug 14 regression)

**Priority:** P1 — security gap
**File:** `src/meridian/lib/workspace/launch.py:351`

`_build_workspace_env()` uses `os.environ.copy()`, bypassing `sanitize_child_env()` that was added for the run execution path. Workspace supervisors inherit the full parent environment including secrets.

**Fix:** Route workspace env through `sanitize_child_env()` from `exec/spawn.py`, same as run execution. Add workspace-specific pass-through keys if needed.

---

## Task 3: Delete dead code

**Priority:** P2 — cleanup
**Source:** Dead code audit

### 3a: Delete `src/meridian/lib/ports.py`
Entire module is unused. Protocols (`RunStore`, `RunStoreSync`, `WorkspaceStore`, `SkillIndex`, `ContextStore`) have zero inbound imports. Greenfield project — no backwards compat needed.

### 3b: Delete unused methods
- `HarnessRegistry.all` (`src/meridian/lib/harness/registry.py:44`)
- `SQLiteWorkspaceStore.transition` (`src/meridian/lib/adapters/sqlite.py:973`)
- `SQLiteContextStore.unpin` (`src/meridian/lib/adapters/sqlite.py:986`)

### 3c: Remove dead parameter
- `stdout_is_tty` in `normalize_output_format()` (`src/meridian/cli/output.py:36`) — never used, callers pass it but behavior is invariant.

### 3d: Remove legacy shim
- `__all__` re-export comment in `src/meridian/cli/output.py:12-13` — no internal consumers.

---

## Task 4: Consolidate duplicate helpers

**Priority:** P2 — DRY violation
**Source:** Dead code audit

### 4a: Unify `_read_artifact_text` (3 copies)
- `src/meridian/lib/extract/finalize.py:32`
- `src/meridian/lib/extract/report.py:21`
- `src/meridian/lib/extract/files_touched.py:36`

Extract to a shared `extract/_io.py` or add to an existing extract utility.

### 4b: Unify JSON walkers / float coercion (2 copies each)
- `_iter_dicts` in `harness/_common.py:225` and `safety/budget.py:118`
- `_coerce_optional_float` / `_coerce_float` in same files

Extract to a shared utility (e.g., `lib/util/json_helpers.py`).

---

## Task 5: Fix `return` in `finally` SyntaxWarning

**Priority:** P2 — code quality
**File:** `src/meridian/lib/exec/signals.py:88`

`return` inside `finally` in `SignalCoordinator.mask_sigterm` triggers `SyntaxWarning` and can suppress exceptions from the `with` block. Refactor to use a flag variable instead of early return in finally.

---

## Task 6: Improve exception handling observability

**Priority:** P3 — observability
**Source:** Dead code audit + code quality review

### 6a: Log suppressed exceptions in `main.py:318-320`
`with suppress(Exception): cleanup_orphaned_locks(...)` swallows errors silently. Add `logger.debug()` or at minimum `logger.warning()`.

### 6b: Log suppressed exceptions in `ops/workspace.py:225-229`
Same pattern — `except Exception` + nested `suppress(Exception)` during rollback. Add logging.

---

## Task 7: Refactor god-object modules (SRP violations)

**Priority:** P3 — maintainability
**Source:** Code quality review

These are larger refactors that improve maintainability but don't affect behavior. Defer unless doing significant work in these areas.

### 7a: Split `ops/run.py`
Currently combines: model validation, profile resolution, skills/index behavior, permission policy, guardrails, secret parsing, command preview, runtime branching. Consider extracting:
- `ops/_validation.py` (model/prompt validation)
- `ops/_preview.py` (dry-run/command preview logic)

### 7b: Split `exec/spawn.py`
Mixes: child env policy, command construction, retry policy, budget enforcement, guardrails, extraction, artifact IO, finalize persistence. Consider:
- `exec/_env.py` (env sanitization, allowlist)
- `exec/_artifacts.py` (extraction, artifact IO)

### 7c: Split `workspace/launch.py`
Combines: profile/default resolution, skill expansion, permission policy, lock lifecycle, env mutation, process spawning, state semantics. Fix env rollback to restore previous values.

### 7d: Decouple agent.py parser from ops layer
`config/agent.py` lazily imports `meridian.lib.ops` for `_known_mcp_tools`, coupling config parsing to runtime operation registration. Move known MCP tools to a static registry or config-level constant.

---

## Task 8: Parametrize duplicate tests

**Priority:** P3 — test quality
**Source:** Dead code audit

### 8a: Parametrize clean-error tests
`tests/test_cli_ux_fixes.py:142` and `:160` — nearly identical "clean error/no traceback" tests.

### 8b: Parametrize unrecoverable classification tests
`tests/test_exec_errors_slice5a.py:8` and `:13` — same structure.

### 8c: Parametrize stale-report sanitization tests
`tests/test_prompt_slice3.py:92` and `:110` — same pattern.

---

## Dependency Graph

```
Task 1 (P0) ─── independent
Task 2 (P1) ─── independent
Task 3 (P2) ─── independent (3a-3d parallel)
Task 4 (P2) ─── independent (4a, 4b parallel)
Task 5 (P2) ─── independent
Task 6 (P3) ─── independent (6a, 6b parallel)
Task 7 (P3) ─── blocked by Tasks 1-6 (refactor after cleanup)
Task 8 (P3) ─── independent
```

## Review History

| Date | Model | Type | Findings |
|---|---|---|---|
| 2026-02-27 | codex (plan-verify) | Full plan + CLI verification | 22 VERIFIED, 5 PARTIAL, 1 MISSING; 2 new bugs |
| 2026-02-27 | codex (quality) | SOLID/code quality review | 4 NEEDS_REFACTOR, 10 MINOR, rest CLEAN |
| 2026-02-27 | codex (dead-code) | Dead code + legacy audit | 4 DELETE, 3 SIMPLIFY, 3 CONSOLIDATE, 0 TODO |
