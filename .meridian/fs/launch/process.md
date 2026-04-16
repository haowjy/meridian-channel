# launch/process — Subprocess Management

## run_harness_process()

`run_harness_process(launch_context, harness_registry)` in `process.py` is the synchronous entry point for primary (CLI) launches. It receives a pre-built `LaunchContext` (the preview context from `launch_primary()`) and owns the full lifecycle: session allocation → spawn row creation → fork materialization → context rebuild → subprocess execution → state finalization.

### Execution Path

```
Precondition: caller has already built a preview LaunchContext via build_launch_context()

1. session_scope() [session_scope.py]
   - Allocates chat_id (c1, c2, ...)
   - Acquires session lock + lease file
   - Resolves work-item attachment (explicit work_id or preserved from resumed session)

2. spawn_store.start_spawn() → registers spawn as queued
   - runner_pid=os.getpid() recorded in start event
   - I-10: do NOT pre-populate harness_session_id on fork starts

3. materialize_fork() [fork.py] — if session_mode == FORK and harness supports it
   - Called only after spawn row exists (I-10)
   - Sole callsite for adapter.fork_session()

4. build_launch_context() [context.py] — RUNTIME rebuild
   - Updates runtime with actual spawn log dir, report path, state_root, work_id
   - This is the context used for real execution (not the preview context passed in)
   - Produces final argv, env, child_cwd, run_params

5. _run_primary_process_with_capture()
   - PTY mode (if stdin+stdout are ttys): pty.fork() + _copy_primary_pty_output()
   - Pipe mode (non-interactive): subprocess.Popen (no streaming_runner.py involved)

5.5. spawn_store.record_spawn_exited() — exited event written immediately after process exits
   - Wrapped in suppress(Exception) so disk errors don't block finalization
   - Carries raw exit code and timestamp; spawn status stays "running" until finalize

6. Finalization (inline, no enrich_finalize)
   - has_durable_report_completion() checks if report.md exists with completion marker
   - resolve_execution_terminal_state() maps exit code + report presence → status
   - Special case: exit codes 143/-15 (SIGTERM) with durable report →
     terminated_after_completion=True → resolved as succeeded
   - spawn_store.finalize_spawn() → terminal state (origin="launcher")
   
7. observe_session_id() [I-4] — called once post-execution (after finalize_spawn)
   - harness_adapter.observe_session_id() — best-effort, wrapped in suppress(Exception)
   - Updates resolved_harness_session_id and spawn/session records if changed

8. stop_session() [session_store] — via session_scope context manager exit
```

### Two-Phase Context Building

The primary path calls `build_launch_context()` twice:

- **Preview phase** (in `launch_primary()`, `dry_run=True`): resolves policies, builds preview argv for display, detects warnings. Uses a placeholder `report_output_path` (`"<spawn-report-path>"`). No filesystem side-effects.
- **Runtime phase** (inside `run_harness_process()`, after spawn row exists): rebuilds context with real paths — actual `report_output_path`, concrete `state_root`, resolved `work_id`. This is the context that drives real subprocess execution.

The split exists because the spawn row (and thus the real log dir) doesn't exist at preview time.

## Primary PTY Mode

When running with a real terminal (`os.isatty(stdin)` and `os.isatty(stdout)`), `process.py` spawns the harness in a PTY. `_copy_primary_pty_output()` runs a select loop forwarding:
- PTY master → stdout + `output.jsonl` log
- stdin → PTY master

Window resize signals (`SIGWINCH`) are forwarded via `_install_winsize_forwarding()`.  
The parent stdin is set to raw mode for the duration.  
Output is written to `.meridian/spawns/<id>/output.jsonl`.

**The primary path does NOT call `enrich_finalize()`.** That pipeline (usage extraction, session ID extraction, report fallback) is exclusive to the spawn/subagent path in `streaming_runner.py`. The primary path finalizes from exit code + durable report checks directly in `process.py`.

## Async Subprocess Execution (streaming_runner.py)

`execute_with_streaming()` in `streaming_runner.py` is the async executor for subagent spawns (non-primary). It is called by `ops/spawn/execute.py` after the spawn row and session exist. Key behaviors:

- Captures stdout → `output.jsonl`, stderr → `stderr.log`
- Feeds stdin from `run_params.stdin_prompt` if set (stdin-based prompt delivery)
- Runs a report watchdog: if `report.md` appears during execution, can consider spawn done
- Maps raw return codes to meridian exit codes
- After process exit, writes the `exited` event inline (via `record_spawn_exited`)
- Calls `enrich_finalize()` (`extract.py`) to extract and persist usage/session/report artifacts

**Heartbeat task:** `_run_heartbeat_task()` touches `.meridian/spawns/<id>/heartbeat` every 30 seconds. Started when the worker process starts. Cancelled in the **outer `finally`** block — the heartbeat covers the entire active window (`running` + `finalizing`). This is the primary liveness signal the reaper uses; see `state/spawns.md`.

**`mark_finalizing` CAS:** in the finalization `finally` block, after the harness has exited and drain/report extraction and retry handling are complete, `spawn_store.mark_finalizing(...)` is called immediately before `finalize_spawn()`. This is a CAS: acquires spawns flock, checks current status is exactly `running`, appends `status="finalizing"` only if so. Returns `True` on success, `False` on miss (already terminal, reaper won the race, etc.). On miss, the runner logs INFO and proceeds — `finalize_spawn(origin="runner")` still runs. The `finalizing` window is narrow: it signals "terminal state is being committed" rather than "draining output."

**Outer `finally` — heartbeat shutdown:** cancels and awaits the heartbeat task unconditionally, even if `finalize_spawn` raises.

## Signal Handling

`SignalForwarder` and `SignalCoordinator` in `signals.py`:

- `SignalCoordinator` is a process-global singleton managing SIGINT/SIGTERM handlers
- `SignalForwarder` registers with the coordinator for the duration of a subprocess run
- On first SIGINT/SIGTERM: forwarded to child process group via `os.killpg(pgid, signum)`
- On second signal: escalates to SIGKILL immediately
- When no forwarders are registered, previous signal handlers are restored

`SignalCoordinator.mask_sigterm()` context manager suppresses SIGTERM during critical sections (e.g., final state writes).

## Timeout Handling

`timeout.py` provides:

```python
terminate_process(process, grace_seconds=DEFAULT_KILL_GRACE_SECONDS)
  # Sends SIGTERM, waits grace_seconds, then SIGKILL

wait_for_process_exit(process, timeout_seconds)
  # Returns exit code or raises SpawnTimeoutError

wait_for_process_returncode(process, timeout_seconds)
  # Non-raising variant; returns None on timeout
```

Default kill grace is `config.kill_grace_minutes * 60` (default: 2 seconds).  
Guardrail timeout: `config.guardrail_timeout_minutes * 60` (default: 30 seconds).

## Artifact Outputs

Each spawn writes to `.meridian/spawns/<id>/`:
- `output.jsonl` — harness stdout (JSONL stream events or raw text)
- `stderr.log` — harness stderr
- `tokens.json` — token usage (extracted from output stream)
- `report.md` — extracted report (written by `enrich_finalize()` on spawn path; checked by primary path for durable completion)

Spawn directories contain durable artifacts plus the runner heartbeat file. Runtime coordination (PIDs, exit status, timestamps) lives in the `spawns.jsonl` event stream. The `heartbeat` file is touched every 30s by the runner and read by the reaper for liveness.

## Error Classification

`errors.py` classifies subprocess failures:

- `ErrorCategory.INFRA` — meridian-level error (process didn't start, OOM, etc.)
- `ErrorCategory.HARNESS` — harness exited non-zero
- `should_retry(exit_code, category)` — whether to attempt retry

Retries are controlled by `config.max_retries` and `config.retry_backoff_seconds`.
