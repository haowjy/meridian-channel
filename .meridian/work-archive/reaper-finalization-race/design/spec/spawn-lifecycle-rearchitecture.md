# Behavioral Specification: Spawn Lifecycle Rearchitecture

## Context

The spawn lifecycle has a structural gap: the harness process can exit before the runner finishes post-exit work (pipe drain, report extraction, artifact persistence, terminal event append). The current reaper is a 500-line state machine that infers liveness from PID files and filesystem markers — both unreliable and Unix-specific. This rearchitecture closes the gap by splitting exit recording from finalization in the event stream, eliminates runtime coordination files, and replaces all PID liveness checks with cross-platform psutil.

## EARS Statements

### Event stream: `exited` event

- **SLR-1**: When `spawn_and_stream` returns (harness process exited, pipes drained or timed out), the runner **shall** immediately append an `exited` event to `spawns.jsonl` carrying the exit code and timestamp, before beginning report extraction or enrichment.

- **SLR-2**: The `exited` event **shall** carry at minimum: `spawn_id`, `exit_code` (raw process exit code), and `exited_at` (ISO 8601 UTC timestamp).

- **SLR-3**: The `exited` event **shall not** carry report content, duration, cost, or token usage — those belong exclusively to the `finalize` event.

- **SLR-4**: When an `exited` event exists for a spawn but no `finalize` event exists yet, the spawn's projected status **shall** remain `running` (the runner is still alive doing post-exit work). The `exited` event is informational, not terminal.

### Event stream: `finalize` event (unchanged semantics)

- **SLR-5**: The existing `finalize` event remains the sole terminal event. It **shall** continue to carry status, exit_code, duration, cost, tokens, and error. Projection semantics (first-terminal-event-wins) are unchanged.

### Reaper: trivial liveness check

- **SLR-6**: When a spawn has no `exited` event and no `finalize` event, the reaper **shall** check whether the runner process PID (from the event stream) is alive using psutil. If the PID is dead and the spawn is not within startup grace, the reaper **shall** finalize the spawn as failed with error `orphan_run`.

- **SLR-7**: When a spawn has an `exited` event but no `finalize` event, the reaper **shall** check whether the runner process PID is alive using psutil. If the runner PID is alive, the reaper **shall not** stamp any terminal state — the runner is still finalizing.

- **SLR-8**: When a spawn has an `exited` event but no `finalize` event, and the runner PID is dead (psutil), the reaper **shall** finalize the spawn using the existing durable-report-completion logic: if `report.md` exists with valid content, finalize as succeeded; otherwise finalize as failed with error `orphan_finalization`.

- **SLR-9**: The reaper **shall not** use grace periods, heartbeat staleness detection, or stale-threshold timers for spawns that have an `exited` event. The `exited` event is definitive proof the harness exited; only runner liveness matters after that point.

- **SLR-10**: The reaper **shall** retain startup grace period logic for spawns with no `exited` event and no `finalize` event, to handle the window between spawn start and harness process creation.

### psutil-based liveness

- **SLR-11**: All process liveness checks **shall** use `psutil.pid_exists()` and `psutil.Process(pid).create_time()` for PID-reuse detection, replacing `/proc/stat` parsing and `os.kill(pid, 0)`.

- **SLR-12**: PID-reuse detection **shall** compare `psutil.Process(pid).create_time()` against the `started_at` timestamp from the spawn's `start` event (converted to epoch). If the process was created after the spawn started plus a tolerance window, the PID has been reused and the original process is dead.

- **SLR-13**: Process liveness checks **shall** work on Linux, macOS, and Windows without platform-specific branches.

- **SLR-14**: When psutil raises `NoSuchProcess` or `AccessDenied`, the liveness check **shall** return dead or alive respectively, consistent with current `os.kill` behavior.

### Elimination of runtime coordination files

- **SLR-15**: The runner **shall not** write `harness.pid`, `background.pid`, or `heartbeat` files to spawn directories.

- **SLR-16**: The streaming runner **shall not** write `harness.pid` or `heartbeat` files to spawn directories.

- **SLR-17**: The primary process launcher (process.py) **shall not** write `harness.pid` or `heartbeat` files to spawn directories.

- **SLR-18**: Spawn directories after completion **shall** contain only durable artifacts: `prompt.md`, `output.jsonl`, `stderr.log`, `report.md`, `params.json`, `tokens.json`, and harness-specific output. No PID files, heartbeat files, or marker files.

- **SLR-19**: The `cleanup_terminal_spawn_runtime_artifacts()` function **shall** be removed or made a no-op, since there are no runtime artifacts to clean up.

### PID sourcing from event stream

- **SLR-20**: The reaper **shall** obtain worker PIDs exclusively from the spawn event stream (`start` and `update` events carry `worker_pid` and `wrapper_pid`), not from PID files.

- **SLR-21**: The runner **shall** record the runner process PID (the process that owns finalization) in the event stream. For foreground spawns, this is `os.getpid()` of the runner process. For background spawns, this is the wrapper PID already recorded.

- **SLR-22**: The event stream **shall** carry a `runner_pid` field identifying the process responsible for finalization. For foreground and primary harness spawns (where the runner is the current process), `runner_pid` **shall** be set in the `start` event. For background spawns (where the runner is a wrapper subprocess created after the start event), `runner_pid` **shall** be set in the first `update` event after the wrapper launches. The reaper reads `runner_pid` from the projected SpawnRecord, which merges both sources.

### No backward compatibility

- **SLR-23**: The reaper **shall** assume all active spawns have `runner_pid` and will emit `exited` events. No legacy fallback paths for old-style spawns. Old `spawns.jsonl` can be wiped on upgrade.

### Visibility improvements

- **SLR-26**: `meridian spawn show` **shall** display the lifecycle state during post-exit finalization: when an `exited` event exists but no `finalize` event, the display **shall** show `running (exited N, awaiting finalization)` where N is the exit code.

- **SLR-27**: `meridian spawn list` **shall** show spawns that have `exited` but not `finalize` as `running` (consistent with projected status) but with a visual indicator of the exited sub-state.

- **SLR-28**: `meridian spawn wait` **shall** by default wait for the `finalize` event (current behavior). A future `--on-exit` flag may allow returning on `exited` — but that is out of scope for this change.

### Background path parity

- **SLR-29**: Background spawns (wrapper-mediated) **shall** record the wrapper PID as `wrapper_pid` and the harness child PID as `worker_pid` in the event stream, as they do today.

- **SLR-30**: The background wrapper process **shall** write the `exited` event when its harness child process exits, following the same protocol as the foreground runner.

- **SLR-31**: For background spawns, the reaper's post-`exited` liveness check **shall** verify the wrapper PID (the process responsible for finalization), not the harness child PID.

### Streaming runner parity

- **SLR-32**: The streaming runner (`streaming_runner.py`) **shall** write the `exited` event when its connection drain completes or its subprocess exits, following the same protocol as the standard runner.

- **SLR-33**: The streaming runner **shall not** write `harness.pid` or `heartbeat` files.

### Reaper size constraint

- **SLR-34**: The reaper module after rearchitecture **shall** be under 80 lines of logic (excluding imports, docstrings, and type definitions). The current 500-line state machine is replaced by a single branching check.
