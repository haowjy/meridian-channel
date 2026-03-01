# Meridian-Channel Remaining Gaps

**Status:** Post-refactor target state (2026-02-28)

This lists gaps that remain **after** the current implementation plan. Items solved by this plan are tracked as closed and should not be re-opened. Items intentionally deferred by scope are tracked separately.

## Closed by This Plan

- SQLite removed everywhere (including skill registry)
- `space.md` replaced by `space.json`
- Runtime path normalized to `.meridian/.spaces/<id>/`
- Session model upgraded to multi-harness-per-space (`sessions.jsonl` + `sessions/*.lock`)
- `active-spaces/` removed
- Legacy commands removed (`migrate run`, `export space`, `skills reindex`)
- Context-aware CLI splits human vs agent help based on `MERIDIAN_SPACE_ID`
- MCP surface restricted to agent-mode commands only
- `doctor` is canonical command (renamed from `diag repair`)
- Auto-create space on `run spawn` (operation layer — works for both CLI and MCP)
- `supervisor` terminology renamed to `primary`/`harness` throughout codebase
- Space status simplified to 2-state enum (`active`, `closed`)
- `space.json` atomic writes + per-space locking
- `doctor` auto-repairs (no separate check/repair modes)
- flock NFS limitation documented
- `meridian start` as top-level launch command with default auto-resume behavior and `--new`/`--space`/`--continue` flags
- `run spawn` + `run continue` split for new-vs-continued conversations
- `run retry` intentionally cut
- Output format by mode (agent=JSON, human=text)
- JSONL self-healing readers (truncated trailing lines)
- Schema versioning (`v: 1` in JSONL, `schema_version: 1` in space.json)
- Error message standard (`[CODE] + cause + next action`)
- Cooperative security model documented
- `sessions.jsonl` stores `harness_session_id` for session-to-harness mapping
- `MERIDIAN_SESSION_ID` env var set by `meridian start` with chat aliases (`c1`, `c2`, ...)
- `space.json` simplified (removed description, labels, pinned_files, last_activity_at)
- `space show` includes session history with copy-paste continue commands
- Config conventions standardized (layered merge, override via `--config`/`MERIDIAN_CONFIG`, and `meridian init` self-documenting commented template)

## Intentionally Deferred (Not Gaps)

### 1. All `fs` commands deferred

Current scope cuts `fs` commands entirely. Agents operate directly in `$MERIDIAN_SPACE_FS/` with shell or harness file tools.

Impact:
- Low for shell-capable agents (`MERIDIAN_SPACE_FS` + native tools)
- Low for MCP clients that invoke harness tools for file operations

Priority: Medium

### 2. All context commands deferred

`context list/pin/unpin` are intentionally cut from MVP. Agents use `MERIDIAN_SPACE_ID` for orientation and manage file context explicitly through `$MERIDIAN_SPACE_FS/` plus prompt references.

Priority: Low (may not be needed if env-var + fs-based patterns work well)

## Remaining Gaps (Post-Plan)

### 1. No cross-space query/index layer

There is no built-in cross-space search/aggregation service.

Expected workaround:
- Shell-based scans/grep over `.meridian/.spaces/*`

Impact:
- Medium for large installations
- Low at current target scale (dozens of spaces, hundreds of runs)

Priority: Low

### 2. Run artifact retention is unbounded

Run artifacts under `runs/<run-id>/` are never auto-cleaned.

Impact:
- Storage growth over time
- Manual cleanup policy required outside core runtime

Priority: Medium

### 3. Harness lifecycle normalization remains deferred

Not part of this refactor:
- Unified lifecycle hooks across harness adapters
- Cross-harness error normalization taxonomy
- Built-in retry policy for transient harness failures

Priority: Medium

### 4. Multi-harness E2E validation coverage is incomplete

Plan explicitly defers full Codex/OpenCode E2E coverage due to upstream constraints.

Priority: Medium

### 5. Adversarial agent security model deferred

MVP uses cooperative trust model (same-user local trust). No hard sandbox, capability tokens, or per-space OS isolation. Shell access bypasses all path validation.

Priority: Medium (needed if multi-tenant or adversarial scenarios arise)

### 6. Space metadata enrichment deferred

`space.json` stripped to minimal fields for MVP. Deferred: `description`, `labels`.

Priority: Low

## Recommendations

1. Define a lightweight retention/archival policy for `runs/` artifacts.
2. Add adapter-level lifecycle/error normalization as a separate hardening phase.
3. Add cross-harness E2E suites once upstream blockers clear.
4. Re-evaluate whether any context command surface is needed beyond env vars and explicit file references.
5. Add per-space sandboxing if adversarial agent model becomes a requirement.
