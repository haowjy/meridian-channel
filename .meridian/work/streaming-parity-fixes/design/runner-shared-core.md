# Runner Shared Core

## Purpose

Collapse the duplication that materially worsened between `runner.py` (958 lines) and `streaming_runner.py` (1189 lines) after the v1 refactor. Both runners now carry independent copies of constants, Claude preflight, env-building, and spec-construction logic, with no shared source of truth. v2 extracts a `LaunchContext` + `prepare_launch_context(...)` shared entry point that both runners call. This doc resolves M6 (escalated from LOW to MEDIUM by the p1411 review), prevents the ordering divergence in M3 from recurring, and sets up L11 (full runner decomposition) as a scoped follow-up rather than a prerequisite.

## Scope

**In scope for this work item:**

- Extract constants (timeouts, base commands, blocked env vars) to `launch/constants.py`.
- Extract the Claude child-cwd + preflight flow to a shared helper so both runners call it identically.
- Extract a `prepare_launch_context(plan, run_params, perms) -> LaunchContext` function that both runners use to produce the fully-resolved spec, env overrides, child cwd, and execution context.
- Each runner becomes a thin caller over `prepare_launch_context(...)` + its transport-specific launch step + shared drain/finalize steps (drain/finalize extraction is a stretch goal).
- Generic text utilities (`dedupe_nonempty`, `split_csv_entries`) move out of `claude_preflight.py` into `launch/text_utils.py` (L4).

**Out of scope (follow-up L11):**

- Full decomposition of runner.py / streaming_runner.py into prepare/launch/drain/finalize modules. This is the correct long-term shape but represents a larger refactor than the streaming-parity work justifies. The shared launch context is the bridge — once it's in place, follow-up work can decompose the surrounding scaffolding incrementally.

## Target Shape

### Layer Overview

```
┌─────────────────────────────────────┐
│ runner.py (subprocess)              │
│   ctx = prepare_launch_context(...) │
│   command = adapter.build_command(  │
│     ctx.run_params, ctx.perms)      │
│   run subprocess ...                │
│   drain + finalize                  │
└─────────────────────────────────────┘
            ↓ calls
┌─────────────────────────────────────┐
│ launch/core.py                      │
│   LaunchContext dataclass           │
│   prepare_launch_context(...)       │
│     - resolve child cwd             │
│     - run Claude preflight          │
│     - build env                     │
│     - build SpawnParams             │
│     - call adapter.resolve_spec(...)│
│   RunResult / DrainOutcome          │
└─────────────────────────────────────┘
            ↑ calls
┌─────────────────────────────────────┐
│ streaming_runner.py                 │
│   ctx = prepare_launch_context(...) │
│   connection = await manager        │
│     .start_spawn(config, ctx.spec)  │
│   drain + finalize                  │
└─────────────────────────────────────┘
```

### LaunchContext

```python
# src/meridian/lib/launch/core.py
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.harness.adapter import PermissionResolver, SpawnParams
from meridian.lib.harness.launch_spec import ResolvedLaunchSpec
from meridian.lib.safety.permissions import PermissionConfig


@dataclass(frozen=True)
class LaunchContext:
    """Fully-resolved launch state shared by subprocess and streaming paths.

    Every field is deterministic from (plan, run_params, perms). The same
    inputs produce byte-identical contexts regardless of which runner
    calls prepare_launch_context — this is the parity contract.
    """

    # Inputs as captured
    run_params: SpawnParams
    perms: PermissionResolver

    # Resolved state
    spec: ResolvedLaunchSpec       # the harness-specific subclass
    child_cwd: Path                # may differ from execution_cwd for Claude
    env: dict[str, str]            # child env after sanitization
    env_overrides: dict[str, str]  # overrides layer used to build env
    permission_config: PermissionConfig  # convenience handle for loggers

    # Transport hints
    report_output_path: Path
```

### `prepare_launch_context`

```python
def prepare_launch_context(
    *,
    plan: PreparedSpawnPlan,
    execution_cwd: Path,
    state_root: Path,
    repo_root: Path,
    passthrough_args: tuple[str, ...],
    report_output_path: Path,
    harness_id: HarnessId,
) -> LaunchContext:
    """Produce the shared LaunchContext for one spawn.

    Both runners call this once per spawn. It:
      1. Resolves the child cwd for Claude (or echoes execution_cwd).
      2. Runs Claude parent-permission forwarding if CLAUDECODE is set.
      3. Constructs SpawnParams from the plan + resolved cwd.
      4. Calls adapter.resolve_launch_spec(params, perms) via the
         harness bundle.
      5. Builds the child env using the adapter's env_overrides +
         shared sanitization.
    """

    bundle = get_harness_bundle(harness_id)
    adapter = bundle.adapter
    perms = plan.execution.permission_resolver

    # (1) + (2): Claude preflight + child cwd
    child_cwd = execution_cwd
    expanded_args = list(passthrough_args)
    resolved_cwd = resolve_child_execution_cwd(
        repo_root=execution_cwd,
        spawn_id=plan.spawn_id,
        harness_id=harness_id.value,
    )
    if resolved_cwd != execution_cwd:
        child_cwd = resolved_cwd
        child_cwd.mkdir(parents=True, exist_ok=True)
        if harness_id == HarnessId.CLAUDE:
            expanded_args.extend(("--add-dir", str(execution_cwd)))
            additional_dirs, parent_tools = read_parent_claude_permissions(
                execution_cwd
            )
            for additional_dir in additional_dirs:
                expanded_args.extend(("--add-dir", additional_dir))
            # Note: --allowedTools dedupe happens inside the Claude
            # projection function, not here. Parent tools flow through
            # as merged extra_args; the projection collapses duplicates
            # using _merge_allowed_tools. See transport-projections.md H2.
            expanded_args = list(merge_allowed_tools_flag(
                tuple(expanded_args), parent_tools
            ))

    # (3): SpawnParams
    run_params = SpawnParams(
        prompt=plan.prompt,
        model=plan.model,
        effort=plan.effort,
        skills=plan.skills,
        agent=plan.agent_name,
        adhoc_agent_payload=plan.adhoc_agent_payload,
        extra_args=tuple(expanded_args),
        repo_root=child_cwd.as_posix(),
        mcp_tools=plan.mcp_tools,
        continue_harness_session_id=plan.session.harness_session_id,
        continue_fork=plan.session.continue_fork,
        report_output_path=report_output_path.as_posix(),
        appended_system_prompt=plan.appended_system_prompt,
        interactive=plan.interactive,
    )

    # (4): Resolved spec
    spec = adapter.resolve_launch_spec(run_params, perms)

    # (5): Env
    runtime_overrides = {
        "MERIDIAN_REPO_ROOT": execution_cwd.as_posix(),
        "MERIDIAN_STATE_ROOT": resolve_state_paths(repo_root).root_dir.resolve().as_posix(),
    }
    merged_overrides = dict(plan.env_overrides)
    merged_overrides.update(runtime_overrides)
    env = build_harness_child_env(
        base_env=os.environ,
        adapter=adapter,
        run_params=run_params,
        permission_config=perms.config,
        runtime_env_overrides=merged_overrides,
    )

    return LaunchContext(
        run_params=run_params,
        perms=perms,
        spec=spec,
        child_cwd=child_cwd,
        env=env,
        env_overrides=merged_overrides,
        permission_config=perms.config,
        report_output_path=report_output_path,
    )
```

Both runners call this exactly once per spawn. The rest of the runner becomes transport-specific:

```python
# src/meridian/lib/launch/runner.py (subprocess)
ctx = prepare_launch_context(...)
command = bundle.adapter.build_command(ctx.run_params, ctx.perms)
# spawn subprocess using ctx.env, ctx.child_cwd, command
# drain, finalize, write report
```

```python
# src/meridian/lib/launch/streaming_runner.py
ctx = prepare_launch_context(...)
connection = await manager.start_spawn(config, ctx.spec)
# subscribe to events, drain, finalize
```

### Constants Extraction

```python
# src/meridian/lib/launch/constants.py
from typing import Final

# Command timeouts
DEFAULT_HARNESS_TIMEOUT_SECONDS: Final[float] = 3600.0
DEFAULT_REQUEST_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_CONNECT_TIMEOUT_SECONDS: Final[float] = 10.0

# Default infra exit code for "runner died before harness exited"
DEFAULT_INFRA_EXIT_CODE: Final[int] = 99

# Blocked child env vars
CLAUDE_BLOCKED_CHILD_ENV_VARS: Final[frozenset[str]] = frozenset({
    "CLAUDECODE",
    "CLAUDE_PARENT_SESSION_ID",
})

# Other per-harness constants...
```

Both runners import from `constants.py`. Grep across the tree to verify no duplicate definitions remain.

### Claude Preflight Module

`src/meridian/lib/launch/claude_preflight.py` stays as the Claude-specific preflight module. It loses its generic helpers (`dedupe_nonempty`, `split_csv_entries`) to `launch/text_utils.py` (L4). Public API:

```python
# src/meridian/lib/launch/claude_preflight.py
def read_parent_claude_permissions(execution_cwd: Path) -> tuple[list[str], list[str]]: ...
def merge_allowed_tools_flag(command: tuple[str, ...], additional: list[str]) -> tuple[str, ...]: ...
def ensure_claude_session_accessible(*, source_session_id, source_cwd, child_cwd) -> None: ...
```

Both runners (via `prepare_launch_context`) use these. The actual `--allowedTools` dedupe at the final command-build step is handled by `_merge_allowed_tools` inside `projections/claude.py` (see transport-projections.md H2 resolution), so `merge_allowed_tools_flag` becomes a preflight-only helper that folds parent-allowed tools into the extra-args list. The projection does the final dedupe.

### Why Not Fully Decompose Now?

Full decomposition of both runners into prepare/launch/drain/finalize modules is the correct long-term shape. The reason it's deferred:

1. **Scope discipline.** The streaming-parity work item is already re-shaping the type contract, projection discipline, permission flow, and shared preflight. A full decomposition would also move signal handling, heartbeat management, and finalize logic. That's a separate refactor with its own risk profile.
2. **Landing discipline.** Partial decomposition is worse than no decomposition — half-extracted modules with unclear ownership create more silent drift, not less.
3. **Bridge first, restructure second.** The `LaunchContext` + `prepare_launch_context` bridge gives the two runners a single source of truth for the parts that diverged. Once that's stable, L11 can decompose the remaining scaffolding without risking the parity contract.

L11 is tracked as an explicit follow-up in the decision log and in `plan/status.md`.

## Parity Contract

A **context parity test** asserts that `prepare_launch_context(...)` produces the same `LaunchContext` regardless of which runner called it. The test fixture:

1. Constructs a `PreparedSpawnPlan` with all fields populated.
2. Calls `prepare_launch_context` twice (identical inputs).
3. Asserts the two `LaunchContext` instances are equal (frozen dataclass equality).
4. Asserts the `.spec`, `.env`, `.run_params`, `.child_cwd`, `.env_overrides` fields match byte-for-byte.

A separate **subprocess/streaming parity test** asserts that for an identical `LaunchContext`, the subprocess command and the streaming spec produce identical spec-derived args (via the shared projection function). This catches any future attempt to reintroduce a divergence.

## Interaction with Other Design Docs

- **Typed harness** ([typed-harness.md](typed-harness.md)) — `HarnessBundle` lookup is where `prepare_launch_context` gets the adapter. The shared core depends on the bundle registry.
- **Launch spec** ([launch-spec.md](launch-spec.md)) — `adapter.resolve_launch_spec(params, perms)` is the single factory call.
- **Permission pipeline** ([permission-pipeline.md](permission-pipeline.md)) — `plan.execution.permission_resolver` must be non-None; `prepare_launch_context` asserts this at entry and fails loudly if the plan lied.
- **Transport projections** ([transport-projections.md](transport-projections.md)) — the shared projections are the downstream consumers of the spec that `prepare_launch_context` produces.
