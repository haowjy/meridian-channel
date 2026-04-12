# Requirements: Spawn Lifecycle Rearchitecture

## Problem

The spawn reaper is a 500-line state machine that exists because of a gap between "harness process exits" and "terminal event gets written." This gap causes false orphan_run classifications (issue #14, p1579), stale status reporting (issue #10), and relies entirely on Unix-specific PID detection (`/proc/stat`). Runtime PID files clutter spawn directories and can be accidentally broken by users.

## Direction

Eliminate the gap instead of building detection around it. Split exit recording from finalization so the event stream knows the harness exited the instant it happens.

### Core Changes

1. **Split terminal events into `exited` + `report`.**
   - `exited` event: written immediately when `process.wait()` returns. Carries exit code, timestamp. This is when the spawn becomes "done" from a status perspective.
   - `report` event: written after pipe drain, report extraction, persistence. Carries report text, duration, enrichment data.
   - Projection merges both to produce the full SpawnRecord.

2. **`psutil` for cross-platform process liveness.**
   - Replace all `/proc/stat` reads and `os.kill(pid, 0)` with `psutil.pid_exists()` + `psutil.Process(pid).create_time()`.
   - Must work on Linux, macOS, and Windows.
   - Eliminates PID-reuse detection complexity (psutil handles it).

3. **Eliminate runtime coordination files from spawn directories.**
   - No `harness.pid`, `background.pid`, `heartbeat`, `finalizing.pid`.
   - PIDs stored in event stream (already are — running/update events carry worker_pid, wrapper_pid).
   - Spawn directories become artifact-only: `prompt.md`, `output.jsonl`, `stderr.log`, `report.md`.

4. **Simplify the reaper to a trivial liveness check.**
   - The only case the reaper handles: spawn has no `exited` event + harness/runner PID is dead (psutil) → orphan.
   - No grace periods, no heartbeat staleness, no PID file inspection, no foreground-vs-background reconciliation paths.
   - The complex state machine is replaced by a single check.

### Visibility Improvements

- `meridian spawn show` displays lifecycle state: `running` → `exited (exit 0), awaiting report` → `succeeded`
- `meridian spawn list` shows spawns in each lifecycle state
- `spawn wait` can return on `exited` (fast) or `--report` (full picture)
- Event stream becomes a rich audit trail of lifecycle moments

## Constraints

- **Cross-platform**: must work on Linux, macOS, and Windows. This is a hard requirement (life sciences pivot).
- **Crash-only design preserved**: atomic writes, read-path reconciliation, no shutdown hooks, no daemon.
- **No backward compatibility required**: per project policy, no backward compat needed. Old spawns.jsonl can be wiped on upgrade. Do not build legacy fallback paths in the reaper.
- **No runtime files in spawn directories**: spawn dirs contain only durable artifacts users might read.
- **The reaper must still catch real orphans**: runner crashes before writing `exited` event are detected via psutil liveness check.

## Success Criteria

1. A spawn whose harness exits cleanly is never misclassified — `exited` event lands immediately.
2. `meridian spawn show` provides meaningful state during every lifecycle phase, including post-exit.
3. No PID files, heartbeat files, or marker files exist in spawn directories.
4. All process liveness checks work on Linux, macOS, and Windows.
5. The reaper is under 50 lines (trivial liveness check, not a state machine).
6. Issues #10 and #14 are resolved by the new architecture.
7. No legacy fallback paths — the reaper assumes all active spawns have the new event types.

## Prior Design (superseded)

The first design iteration proposed a `finalizing.pid` marker file. That design was correct but incremental — it added another runtime file to solve a problem caused by runtime files. This rearchitecture eliminates the category of problem instead of patching it.

Design artifacts from the first iteration are in `design/` — the spec, architecture, feasibility, and refactors files reflect the superseded marker-file approach and should be replaced.
