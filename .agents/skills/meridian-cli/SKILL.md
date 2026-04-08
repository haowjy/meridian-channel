---
name: meridian-cli
description: "Mental model and principles for the meridian and mars CLIs. Use when an agent needs to discover what meridian can do, learn a subcommand, diagnose a failure, or understand why meridian behaves the way it does. Points at `meridian --help` and `meridian mars --help` as the canonical reference rather than duplicating them."
---

# meridian-cli

## 1. What Meridian Is

Meridian is a thin coordination layer for multi-agent systems. It is not a runtime, database, or workflow engine. It launches subagents through harness adapters, persists spawn and session state under `.meridian/`, and exposes that state through one CLI.

State on disk is the source of truth. If it is not visible in `.meridian/` files, it does not exist. There is no daemon and no long-lived in-memory state outside CLI processes.

## 2. CLI Surface by Command Group

| Command group | What it covers | Where to learn more |
|---|---|---|
| `meridian spawn` | Create, wait, list, show, log, cancel, stats, reports for subagent runs | `meridian spawn --help` |
| `meridian work` | Work item lifecycle, dashboard, session listing | `meridian work --help` |
| `meridian session` | Read and search harness session transcripts | `meridian session --help` |
| `meridian models` | Model catalog and routing guidance | `meridian models list` |
| `meridian config` | Resolved config inspection and overrides | `meridian config --help` |
| `meridian doctor` | Health check and orphan reconciliation | `meridian doctor --help` |
| `meridian mars` | Bundled mars CLI for `.agents/` package management | `meridian mars --help` |

## 3. Principles `--help` Cannot Teach

**Output mode discipline.** Agent mode defaults to JSON while interactive terminals may default to text. Parse `spawn_id` and `status` from JSON responses, and avoid scraping prose from text output.

**Files as authority.** Spawn and session state lives under `.meridian/` as JSONL events plus per-spawn artifact directories. Never hand-edit `spawns.jsonl` or `sessions.jsonl`.

**Idempotent operations.** `meridian mars sync`, `meridian doctor`, and read-path reconcilers are built to converge when rerun. Re-running after interruption should reconcile state rather than duplicate side effects.

**Config precedence.** Resolution is per field: CLI flag, then `MERIDIAN_*` environment variable, then profile YAML, then project config, then user config, then harness defaults. A CLI model override must also drive derived harness resolution for that field. For concrete keys and defaults, see [`resources/configuration.md`](resources/configuration.md).

**Parent session inheritance.** `$MERIDIAN_CHAT_ID` is inherited from the spawning session. Session reads and searches default to that parent context, which is where upstream decisions usually live.

**Crash-only design.** Writes use atomic tmp+rename, reads tolerate truncation, and reconciliation happens on read paths. Recovery is startup behavior, not a shutdown hook.

## 4. Mars in One Section

Mars materializes `.agents/` from sources declared in `mars.toml`, and `meridian mars ...` is the bundled entrypoint. `mars.toml` is the committed source manifest, `mars.lock` is committed generated state, and `mars.local.toml` is local override state. Drift and integrity checks live in `meridian mars list --status` and `meridian mars doctor`. Do not edit `.agents/` directly; regenerate it with `meridian mars sync`.

For full command coverage, use `meridian mars --help`. For the full `mars.toml` schema reference, see [`resources/mars-toml-reference.md`](resources/mars-toml-reference.md).

## 5. Diagnostics

### Common Failure Modes

| Symptom | Likely cause | First move |
|---|---|---|
| `orphan_run` / `orphan_stale_harness` | Harness died without finalizing | Relaunch after read-path reconciliation updates the record |
| `missing_wrapper_pid` / `missing_worker_pid` | Harness crashed during startup | Confirm harness binaries are installed and on `$PATH` |
| `missing_spawn_dir` | Crash during launch before spawn artifacts stabilized | Relaunch the spawn |
| Exit 127 or 2 with empty report | Harness binary missing from `$PATH` | Install or fix PATH for the selected harness |
| Exit 143 or 137 | Process terminated externally | Check `meridian spawn show <id>` first; if status is `succeeded`, signal hit during cleanup and no retry is needed. Otherwise check host logs for OOM or external kill, then retry |
| Timeout exit | Runtime budget exceeded | Increase timeout or split task into smaller spawns |
| Model/API error in `stderr.log` | Model unavailable or API rejected request | Check `meridian models list` and provider credentials |

Use this sequence when diagnosing: `meridian spawn show` -> `meridian spawn log` -> `meridian session log` -> `meridian doctor` -> raw `spawns.jsonl` with `jq` as last resort.
For deeper state-debugging flows and low-level log inspection, see [`resources/debugging.md`](resources/debugging.md).

### Spawn Artifact Layout

Each spawn writes artifacts under `.meridian/spawns/<spawn_id>/`.

| File | Contents |
|---|---|
| `report.md` | Final report when the spawn reached report emission |
| `output.jsonl` | Raw harness stdout (prefer `meridian spawn log`) |
| `stderr.log` | Harness stderr, warnings, and errors |
| `prompt.md` | Prompt materialized for the harness |
| `harness.pid` | Foreground harness PID file |
| `heartbeat` | Liveness touch file while spawn is active |

## 6. Sessions

`meridian session log <ref>` reads a transcript by chat id, spawn id, or harness session id. Segment `-c 0` reads latest compacted segment; increment `-c` to walk older segments. `meridian session search <query> <ref>` searches case-insensitively across segments and returns navigation context.

`meridian work sessions <work_id>` lists sessions tied to a work item, and `--all` includes archived history. Combined with parent-session inheritance, this is the standard path to recover decision history for ongoing work.

For flag details, use `meridian session --help` and `meridian work sessions --help`.

## 7. Environment Variables

| Variable | Purpose |
|---|---|
| `MERIDIAN_STATE_ROOT` | Override `.meridian/` location |
| `MERIDIAN_DEPTH` | Spawn nesting depth (`>0` means inside a spawn) |
| `MERIDIAN_FS_DIR` | Shared long-lived filesystem directory |
| `MERIDIAN_WORK_DIR` | Active work-item scratch directory |
| `MERIDIAN_CHAT_ID` | Inherited parent session id |

## 8. Where to Go Next

- For delegation patterns and model routing, load `meridian-spawn`.
- For work lifecycle and artifact placement, load `meridian-work-coordination`.
- For capability-limit escalation flow, load `meridian-privilege-escalation`.
