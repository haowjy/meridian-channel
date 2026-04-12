# Decision Log

## Superseded Decisions (D1-D7)

Decisions D1-D7 applied to the prior `finalizing.pid` marker-file design. That design was correct but incremental — it added a runtime file to solve a problem caused by runtime files. The rearchitecture below eliminates the category of problem instead. D1-D7 are preserved in git history.

## D8: Rearchitect instead of patch

**Choice**: Eliminate the reaper state machine entirely rather than add a `finalizing.pid` marker file to the existing design.

**Reasoning**: The marker-file approach (D1-D7) was correct but left the fundamental complexity intact: the reaper still had to inspect PID files, compute staleness, dispatch on launch mode, and handle grace periods. The root cause isn't missing coordination signals — it's that the event stream doesn't model the lifecycle accurately. Splitting exit recording from finalization makes the lifecycle explicit and reduces the reaper to a trivial liveness check.

**Alternatives rejected**:
- `finalizing.pid` marker: Adds another runtime file to a system whose problems stem from runtime files. Correct fix, wrong abstraction level.
- `SpawnStatus("finalizing")`: Too invasive for a transient state. The `exited` event achieves the same signal without schema churn.
- Relaxing first-terminal-event-wins: Would fix p1579 but destroy a valuable invariant.

## D9: `exited` event is informational, not terminal

**Choice**: The `exited` event does not change the spawn's projected status. The spawn remains `running` until `finalize`.

**Reasoning**: The `exited` event represents "harness process exited" — but the spawn isn't done. The runner is still draining pipes, extracting reports, persisting artifacts. Making `exited` terminal would create a new gap: spawns that appear "done" but don't have report data yet. Instead, `exited` is a lifecycle marker that the reaper and display layer use to make better decisions.

**Constraint discovered**: This means `spawn wait` still blocks until `finalize`, not `exited`. A future `--on-exit` flag could unblock earlier, but that's out of scope.

## D10: psutil over custom PID inspection

**Choice**: Use psutil for all process liveness checks, replacing `/proc/stat` parsing and `os.kill(pid, 0)`.

**Reasoning**: The current liveness code is Linux-only (`/proc/stat` for boot time, clock ticks). macOS has no PID-reuse guard. Windows doesn't support `os.kill` for arbitrary PIDs. psutil provides a single API that works everywhere with built-in create_time for PID-reuse detection. It's ~200M downloads/month, pure C extension, no transitive deps.

**Trade-off**: Adds a compiled dependency. Acceptable because: (1) psutil provides pre-built wheels for all platforms, (2) it has no transitive deps, (3) the alternative is maintaining 50 lines of fragile platform-specific PID inspection.

## D11: `runner_pid` in event stream, not PID file

**Choice**: Record the runner process PID (the process responsible for finalization) in the spawn `start` event, not in a PID file.

**Reasoning**: The runner PID answers the reaper's key question: "after `exited`, is the entity doing post-exit work still alive?" Storing it in the event stream rather than a file means: (1) no new runtime files, (2) the PID is available even after the spawn directory is cleaned up, (3) backward compatibility is automatic (old spawns have `runner_pid=None`, reaper falls back to `worker_pid`).

## D12: Delete heartbeat module entirely

**Choice**: Remove `heartbeat.py` and all heartbeat-related code instead of keeping it as optional.

**Reasoning**: The heartbeat mechanism served one purpose: proving to the reaper that a spawn is alive. With the `exited` event and psutil-based liveness, the reaper doesn't need filesystem-based activity signals. The heartbeat added I/O overhead (30-second touch interval), code complexity, and a stale-detection heuristic that was never fully reliable (it's what the current reaper uses for `orphan_stale_harness`, which this rearchitecture eliminates).

## D13: Spawn directories become artifact-only

**Choice**: No PID files, heartbeat files, or marker files in spawn directories. Only durable artifacts.

**Reasoning**: Every runtime file in the spawn directory was a coordination mechanism compensating for gaps in the event stream. With the `exited` event and `runner_pid`, the event stream is self-sufficient. Spawn directories contain only things a user would want to read: `prompt.md`, `output.jsonl`, `stderr.log`, `report.md`, `params.json`, `tokens.json`.

## D14: Retain startup grace for pre-exit spawns

**Choice**: Keep the startup grace period for spawns with no `exited` event and no `finalize` event.

**Reasoning**: There's still a real gap between "spawn started" and "harness process created." During this window, no PID is recorded yet. The grace period handles this window. But unlike the current reaper, the grace period is the *only* timing heuristic — no staleness thresholds, no heartbeat checks, no 5-minute timers.

## D15: New error code `orphan_finalization`

**Choice**: Distinguish runner crash during post-exit finalization (`orphan_finalization`) from runner crash before any exit processing (`orphan_run`).

**Reasoning**: These are different failure modes with different diagnostics. `orphan_run` means neither the harness nor the runner survived. `orphan_finalization` means the harness exited successfully but the runner crashed while processing the results. The latter is much rarer and suggests infrastructure issues, not harness problems.
