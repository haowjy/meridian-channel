# launch/ — Spawn Lifecycle Overview

## What This Is

`src/meridian/lib/launch/` owns the full lifecycle from "caller builds a request" to "harness process exits and artifacts are persisted." It is the composition and execution layer between the policy layer (`ops/spawn/`) and the mechanism layer (harness adapters, state stores).

## Architecture Model

The launch subsystem uses **hexagonal composition** centered on `build_launch_context()` in `context.py`:

```
SpawnRequest + LaunchRuntime  →  build_launch_context()  →  LaunchContext
                                       (sole composition seam)
```

**Driving adapters do not compose.** Each driving adapter:
1. Builds a `SpawnRequest` (caller intent DTO) and a `LaunchRuntime` (environment/surface/runtime inputs)
2. Calls `build_launch_context()` — the factory resolves policies, permissions, prompt, env, argv
3. Executes or observes using the resulting `LaunchContext`

This means all composition logic — policy resolution, permission pipeline, prompt assembly, argv construction, child env — lives in one place. Reviewers check I-1/I-2 to confirm no driving adapter bypasses the factory. See `.meridian/invariants/launch-composition-invariant.md` (13 invariants).

## Three Driving Adapters

### 1. Primary CLI path

`launch_primary()` in `__init__.py`:

```
plan.py:build_primary_spawn_request()   →  SpawnRequest (PRIMARY surface)
plan.py:build_primary_launch_runtime()  →  LaunchRuntime
build_launch_context(..., dry_run=True) →  LaunchContext (preview — for dry-run display)
run_harness_process(preview_context, …) →  ProcessOutcome
```

Inside `run_harness_process()` (`process.py`):
- Allocates session via `session_scope`, creates spawn row (`start_spawn`)
- Materializes fork if needed via `fork.py:materialize_fork()` — only after row exists (I-10)
- **Rebuilds `LaunchContext`** via factory with actual spawn/report/work paths (`report_output_path`, `state_root`, etc.) — this is the runtime context that produces the real argv/env
- Runs `_run_primary_process_with_capture()` (PTY or pipe mode)
- Finalizes inline (exit code + durable report check); no `enrich_finalize`
- Calls `harness_adapter.observe_session_id()` once post-execution (I-4)

Work-item attachment is resolved at policy level in `launch_primary()` before entering `process.py`. `process.py` is pure mechanism.

### 2. Spawn subprocess path

`ops/spawn/execute.py` drives both foreground and background spawns:

- **Foreground** (`execute_spawn_blocking()`): creates spawn row, builds `LaunchContext` (`SPEC_ONLY`), calls `asyncio.run(execute_with_streaming(...))`
- **Background** (`execute_spawn_background()`): creates spawn row, persists `BackgroundWorkerLaunchRequest` to disk, detaches subprocess — background worker then calls `_execute_existing_spawn()` which builds `LaunchContext` and calls `execute_with_streaming()`
- **Prepare** (`ops/spawn/prepare.py:build_create_payload()`): uses factory with `SPAWN_PREPARE` surface and `dry_run=True` for prompt composition and preview argv; returns `resolved_request` with `cli_command` populated

All three use `LaunchArgvIntent.SPEC_ONLY` — the streaming runner operates from typed spec, not subprocess argv.

`streaming_runner.py:execute_with_streaming()` is the async subprocess executor for this path. It handles heartbeat, `mark_finalizing` CAS, `enrich_finalize()`, and `finalize_spawn()`.

### 3. App/streaming HTTP path

`lib/app/server.py` and `cli/streaming_serve.py` use the factory with `SPEC_ONLY` and default surface (`DIRECT`), then use `launch_ctx.spec` to start streaming connections via `SpawnManager`:

```
SpawnRequest + LaunchRuntime(SPEC_ONLY) → build_launch_context() → LaunchContext
spawn_manager.start_spawn(config, launch_ctx.spec)
```

These paths do not use `process.py` or `streaming_runner.py`.

## Core Typed Seam

```python
SpawnRequest     # Caller intent DTO — prompt, model, harness, skills, session, budget, …
                 # Frozen Pydantic. JSON-safe. No derived/cached state (I-5).

LaunchRuntime    # Driving-adapter inputs — surface, state_root, project_paths,
                 # argv_intent, config_snapshot, harness_command_override, …
                 # Frozen Pydantic.

LaunchContext    # Composed launch state — argv, spec, env, run_params, perms,
                 # child_cwd, report_output_path, warnings, resolved_request, …
                 # Frozen dataclass. Complete at construction (I-5).
```

Key enums:

```python
LaunchArgvIntent           # REQUIRED | SPEC_ONLY
  REQUIRED   → subprocess callers need a command tuple
  SPEC_ONLY  → streaming/app callers use typed spec; argv left empty

LaunchCompositionSurface   # DIRECT | PRIMARY | SPAWN_PREPARE
  PRIMARY      → full primary-path composition (session seed, inventory prompt, …)
  SPAWN_PREPARE → spawn path composition (prompt assembly from refs, context_from, …)
  DIRECT       → minimal composition (bypass surface; harness resolved from request only)

LaunchMode                 # background | foreground | app  (in state/spawn_store.py)
```

`LaunchContext.warnings` is the sole channel for composition warnings (I-13). Adapters that silently transform inputs violate I-13.

## Entry Point

`launch_primary()` in `__init__.py`:
```python
def launch_primary(*, repo_root, request, harness_registry) -> LaunchResult
```

Resolves work-item attachment, calls factory for preview context (dry-run), then delegates to `run_harness_process()`. Returns `LaunchResult{command, exit_code, continue_ref, warning}`.

## Module Map

```
launch/
  __init__.py         — launch_primary() public entry point; lazy re-exports
  context.py          — build_launch_context() — SOLE composition surface (I-1)
  request.py          — SpawnRequest, LaunchRuntime, LaunchArgvIntent,
                        LaunchCompositionSurface, SessionRequest, ExecutionBudget
  plan.py             — build_primary_spawn_request(), build_primary_launch_runtime()
                        (primary-path input builders; not a resolver)
  process.py          — run_harness_process(); PTY/pipe capture; primary-path executor
  streaming_runner.py — execute_with_streaming(); async subprocess executor (spawn path)
  policies.py         — resolve_policies(); ResolvedPolicies
  resolve.py          — resolve_skills_from_profile(), resolve_profile_path(), …
  permissions.py      — resolve_permission_pipeline()
  command.py          — resolve_launch_spec_stage(), apply_workspace_projection(),
                        build_launch_argv(), normalize_system_prompt_passthrough_args()
  fork.py             — materialize_fork() — sole callsite for adapter.fork_session()
  prompt.py           — compose_run_prompt_text(); skill injection; inventory prompt
  reference.py        — load_reference_files(); template variable resolution
  run_inputs.py       — ResolvedRunInputs
  env.py              — build_env_plan(); build_harness_child_env(); inherit_child_env()
  cwd.py              — resolve_child_execution_cwd()
  session_scope.py    — session_scope() context manager
  launch_types.py     — ResolvedLaunchSpec, CompositionWarning, PermissionResolver, …
  extract.py          — enrich_finalize() pipeline: usage + session + report (spawn path)
  report.py           — extract_or_fallback_report(); report.md preference
  signals.py          — SignalForwarder, SignalCoordinator; SIGINT/SIGTERM forwarding
  errors.py           — ErrorCategory; classify_error(); should_retry()
  types.py            — LaunchRequest, LaunchResult, SessionMode, SessionIntent, …
  default_agent_policy.py — fallback chain when no agent profile requested
```

## Design Notes

**Factory-centered composition**: All policy, permission, prompt, argv, and env assembly happens inside `build_launch_context()` and its named pipeline stages. Driving adapters are prohibited from reconstructing any of this (I-1, I-2). Adding a new composition concern = one named stage in the factory.

**Two-phase context building in the primary path**: `launch_primary()` calls the factory once (`dry_run=True`) for preview/display. After the spawn row is created, `run_harness_process()` calls the factory again with real paths (`report_output_path`, actual `state_root`, `work_id`). The preview context is used for the initial argv display; the runtime context drives actual execution.

**Policy vs mechanism split**: `launch_primary()` resolves work-item attachment (policy). `process.py` manages subprocesses, state writes, and artifact persistence without caring about work items or override layers (mechanism).

**Crash tolerance**: `streaming_runner.py` writes a `heartbeat` artifact every 30s for the full active window (`running` + `finalizing`). The reaper uses heartbeat recency as its primary liveness signal. `mark_finalizing` CAS (after drain/report work, immediately before `finalize_spawn`) lets the reaper distinguish `orphan_finalization` from `orphan_run`. Runner-origin terminal writes supersede reconciler-origin via the projection authority rule. See `state/spawns.md`.

**DTO discipline**: `SpawnRequest` and `LaunchRuntime` are frozen Pydantic with JSON-safe field types. `LaunchContext` is a frozen dataclass. No `arbitrary_types_allowed`, no `Path` on `SpawnRequest`, no pre-composed intermediate DTOs (I-5). DTOs do not cache derived state — the factory recomputes from inputs.

**Invariant gate**: 13 invariants in `.meridian/invariants/launch-composition-invariant.md`. Reviewers check these on every PR touching `src/meridian/lib/(launch|harness|ops/spawn|app)/` and `src/meridian/cli/streaming_serve.py`.

## Related Docs

- `launch/process.md` — subprocess management, signals, timeouts, exited event recording
- `launch/prompt.md` — prompt assembly, skill injection, template variables
- `launch/reports.md` — report extraction, fallback chain, auto-extracted reports
- `state/spawns.md` — spawn store, event model, terminal merging
- `catalog/agents-and-skills.md` — profile and skill loading
