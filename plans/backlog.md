# Backlog

Issues discovered during development and testing. Add new items at the top.

## Open

### Orphaned runs stay "running" forever after process kill
- **Found:** 2026-03-01, during space plumbing fix testing
- **Severity:** Medium
- **Description:** When a `meridian run spawn` parent process is killed (or crashes), the codex child process orphans and the run record stays `status: "running"` in `runs.jsonl` forever. No cleanup detects the dead process.
- **Context:** `launch.py` already handles this for spaces via `cleanup_orphaned_locks()` (PID-based detection), but the run layer has no equivalent.
- **Fix ideas:** Store child PID in run record, add `cleanup_orphaned_runs()` similar to space lock cleanup, or add a signal handler in `_execute_run_blocking` to finalize on SIGTERM/SIGINT.

### `meridian start` doesn't inject skills via --append-system-prompt
- **Found:** 2026-03-01, during skill preloading investigation
- **Severity:** High
- **Description:** `launch.py:_build_interactive_command()` resolves skills but never injects them via `--append-system-prompt`. The workaround for Claude Code issue #29902 was only added to `_run_prepare.py` (run spawn path), not the primary agent launch path.
- **Plan:** `plans/unify-harness-launch.md` Step 0 (quick fix) + Step 1 (unify pipeline)

### Agent profiles have no default skills
- **Found:** 2026-03-01
- **Severity:** Medium
- **Description:** All agent profiles (coder, reviewer, researcher, orchestrator) have `skills: []`. Should have sensible defaults.
- **Plan:** `plans/unify-harness-launch.md` Step 0

### report.md not overwritten between runs
- **Found:** 2026-03-01, during space plumbing testing
- **Severity:** Medium
- **Description:** Workspace `report.md` persists from prior runs. Two causes: (a) `report_path` isn't a real write target in the execution pipeline, (b) CLI report lookup scans all spaces with repeating run IDs and can return wrong report.
- **Plan:** `plans/space-plumbing-fix.md` Step 1

### `-f @name` reference loading ignores threaded space
- **Found:** 2026-03-01, during space plumbing investigation
- **Severity:** Medium
- **Description:** `src/meridian/lib/prompt/reference.py` reads `os.getenv("MERIDIAN_SPACE_ID")` directly instead of using the threaded space context.
- **Plan:** `plans/space-plumbing-fix.md` Step 2

### Artifact keys lack space component — cross-space collisions
- **Found:** 2026-03-01, during space plumbing investigation
- **Severity:** Medium
- **Description:** Run IDs are per-space (`r1`, `r2`...) but artifact keys are `{run_id}/...` with no space prefix. Cross-space collisions possible.
- **Plan:** `plans/space-plumbing-fix.md` Step 3

### Duplicate skill warnings from overlapping skill paths
- **Found:** 2026-03-01
- **Severity:** Low
- **Description:** `.agents/skills/orchestrate/` and `src/meridian/resources/.agents/skills/orchestrate/` both exist, producing noisy warnings on every run.

## Done

(Move completed items here with date.)
