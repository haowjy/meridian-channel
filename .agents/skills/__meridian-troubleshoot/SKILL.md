---
name: __meridian-troubleshoot
description: "Diagnostic and troubleshooting guide for meridian problems. Use when spawns fail unexpectedly, state seems corrupt, the CLI behaves strangely, or you need to run `meridian doctor`. Covers common failure patterns, state recovery, log inspection, and systematic debugging methodology."
---

# Troubleshoot

This is a dormant skill — use it only when something goes wrong. It covers how to diagnose and fix meridian problems systematically.

## Debugging Methodology

Follow this sequence. Stop as soon as you find the cause.

1. **Check spawn status** — `meridian spawn show SPAWN_ID`. Read the `status`, `error`, and `report` fields.
2. **Read the report** — a failed spawn's report often contains the error or the agent's last output.
3. **Check logs** — inspect `stderr.log` in the spawn directory (path shown by `spawn show`).
4. **Run doctor** — `meridian doctor` reconciles stale state and reports warnings.
5. **Inspect state files** — only as a last resort. Read `spawns.jsonl` directly with `jq`.

## `meridian doctor`

Doctor is a health check and auto-repair command. It performs three checks:

1. **Stale session locks** — cleans up session entries for sessions that are no longer active.
2. **Orphan spawns** — runs the reaper to reconcile any active spawns whose processes have died. Detects dead PIDs, stale output (no activity for 5+ minutes), and missing spawn directories.
3. **Configuration** — warns if agents or skills directories are missing from `.agents/`.

```bash
meridian doctor
# ok:            ok
# runs_checked:  12
# repaired:      orphan_runs
```

If `ok` is not `ok`, read the warnings. If `repaired` lists items, doctor already fixed them — just verify the result.

## Common Failure Patterns

### Orphan / Stale Spawn (error: `orphan_run`, `orphan_stale_harness`)

The harness process died without finalizing. The reaper detects this on the next read and marks it failed automatically. No manual cleanup needed — just relaunch.

### Missing Spawn Directory (error: `missing_spawn_dir`)

The spawn's artifact directory was deleted or never created (crash during launch). No state to recover — relaunch.

### Missing PID File (error: `missing_wrapper_pid`, `missing_worker_pid`)

The harness process never wrote its PID file — usually means it crashed on startup. Check `which claude` / `which codex`, install if missing, then relaunch.

### Harness Not Found (exit code 127 or 2)

The harness command (`claude`, `codex`, `opencode`) is not on `$PATH`. Primary launch catches `FileNotFoundError` and returns exit code 2.

**Diagnosis:** `meridian spawn show SPAWN_ID` shows exit code 127 or 2, no report.
**Fix:** Install the harness (`npm install -g @anthropic-ai/claude-code`, etc.) and ensure it is on your `$PATH`.

### Timeout

Spawns that exceed their time limit are killed by the background wrapper.

**Diagnosis:** Check the spawn's `error` field and `stderr.log` for timeout messages.
**Fix:** Increase timeout in config or break the task into smaller steps.

### Process Killed (SIGTERM / SIGKILL)

Exit code 143 (SIGTERM) or 137 (SIGKILL). If a durable report exists and exit code is 143, meridian treats this as success (the harness was terminated after completing its work).

**Diagnosis:** `spawn show` exit code is 143 or 137.
**Fix:** If status is `succeeded`, no action needed. If `failed`, check what killed the process — OOM killer (`dmesg`), manual kill, or system shutdown.

### Model Unavailable

The harness started but the API rejected the model identifier.

**Diagnosis:** `stderr.log` shows authentication or model errors from the provider.
**Fix:** Run `meridian models list` to see available models. Check API keys and billing.

## Log Inspection

Each spawn has a directory at `.meridian/spawns/<SPAWN_ID>/`. Key files:

- `stderr.log` — harness stderr (errors, warnings, debug traces)
- `output.jsonl` — raw harness stdout captured during execution
- `report.md` — the spawn's final report (if it completed far enough)
- `prompt.md` — the prompt sent to the harness
- `harness.pid` / `background.pid` — PID files for foreground / background spawns
- `heartbeat` — periodically touched while the spawn is alive

Get the path from CLI output rather than constructing it manually:

```bash
meridian spawn show SPAWN_ID
# Read "log_path" from the JSON output, then inspect stderr.log there.
```

## State Recovery

### Crash-Only Design

Meridian uses crash-only design: every write is atomic (tmp + rename), every read tolerates truncation, and recovery IS startup. There is no graceful shutdown path — if meridian is killed mid-operation, the next read-path command detects and repairs the state.

The reaper runs automatically on every user-facing read (`spawn list`, `spawn show`, `spawn wait`, dashboard). It checks whether PIDs are alive, guards against PID reuse via `/proc` start-time comparison, and detects stale spawns (no output for 5+ minutes).

### When State Looks Corrupt

If `.meridian/` state seems wrong:

1. Run `meridian doctor` — it reconciles orphans and cleans stale locks.
2. Check `spawns.jsonl` with `jq` — look for spawns stuck in `queued` or `running` with no live process.
3. If `spawns.jsonl` is truncated (crash during write), meridian's JSONL reader skips malformed trailing lines. The data before the truncation point is preserved.

Never manually edit `spawns.jsonl` or `sessions.jsonl`. Use CLI commands and let the reaper handle reconciliation.

### Environment Variables

These override defaults and are useful for debugging:

- `MERIDIAN_STATE_ROOT` — override the `.meridian/` location
- `MERIDIAN_DEPTH` — current nesting depth (>0 means running inside a meridian spawn)
- `MERIDIAN_FS_DIR` — shared filesystem directory
- `MERIDIAN_WORK_DIR` — current work item scratch directory
