# Phase 4: Factory Boundary Rewire

## Goal

Rewrite `build_launch_context()` in `context.py` to accept raw `SpawnRequest` + `LaunchRuntime` instead of `PreparedSpawnPlan`. Make this factory the sole owner of bypass dispatch and dry-run/runtime parity.

## Requirements

### 1. New Factory Signature

Create `build_launch_context()` with this contract:

```python
def build_launch_context(
    *,
    request: SpawnRequest,
    runtime: LaunchRuntime,
    spawn_id: str,
    harness_registry: HarnessRegistry,
    dry_run: bool = False,
) -> LaunchContext | BypassLaunchContext:
    """Build complete launch context from raw inputs."""
```

### 2. Bypass Branch — Sole Owner

When `runtime.harness_command_override` is set:
- Parse and validate the override command
- Run preflight (for argv expansion consistency) 
- Return `BypassLaunchContext` with the passthrough command
- This replaces the bypass logic currently in `plan.py:258-297`

Create `BypassLaunchContext` as a separate type:
```python
@dataclass(frozen=True)
class BypassLaunchContext:
    """Launch context for MERIDIAN_HARNESS_COMMAND bypass."""
    argv: tuple[str, ...]
    env: Mapping[str, str]
    child_cwd: Path
```

### 3. Pipeline Stages (Normal Path)

For non-bypass launches, call stages in this order:
1. `resolve_policies()` — from `launch/policies.py`
2. `resolve_permission_pipeline()` — from `launch/permissions.py`
3. `compose_prompt()` / prompt assembly
4. `build_resolved_run_inputs()` — from `launch/run_inputs.py`
5. `materialize_fork()` — only when `not dry_run and session.continue_fork`
6. `resolve_launch_spec_stage()` — from `launch/command.py`
7. `apply_workspace_projection()` — from `launch/command.py`
8. `build_launch_argv()` — from `launch/command.py`
9. `build_env_plan()` — from `launch/env.py`

### 4. LaunchContext Updates

Update `LaunchContext` to be the executor's complete input:
```python
@dataclass(frozen=True)
class LaunchContext:
    """Complete launch context ready for execution."""
    argv: tuple[str, ...]
    env: Mapping[str, str]
    child_cwd: Path
    run_params: ResolvedRunInputs
    perms: PermissionResolver
    spec: ResolvedLaunchSpec
    report_output_path: Path
    harness_adapter: SubprocessHarness  # For post-exec observation
```

### 5. Dry-Run Parity

When `dry_run=True`:
- Still run preflight for argv expansion
- Skip `materialize_fork()` 
- Return the same `LaunchContext` shape that runtime would produce
- Argv must match what runtime would execute

### 6. Project Paths from LaunchRuntime

Use `runtime.project_paths_repo_root` and `runtime.project_paths_execution_cwd` to construct `ProjectPaths`:
```python
project_paths = ProjectPaths(
    repo_root=Path(runtime.project_paths_repo_root),
    execution_cwd=Path(runtime.project_paths_execution_cwd),
)
```

## Files to Modify

- `src/meridian/lib/launch/context.py` — Add `build_launch_context()`, `BypassLaunchContext`
- `src/meridian/lib/launch/request.py` — Ensure SpawnRequest has all needed fields

## Files NOT to Modify Yet

- `launch/plan.py` — Keep existing `resolve_primary_launch_plan()` for now (drivers migrate in Phase 5)
- `launch/process.py` — Keep using `ResolvedPrimaryLaunchPlan` (Phase 5 migrates it)
- Driver adapters — Phase 5

## Exit Criteria

1. `build_launch_context()` exists and accepts raw `SpawnRequest` + `LaunchRuntime`
2. `BypassLaunchContext` exists for bypass dispatch
3. The new factory compiles and passes type checking (`uv run pyright`)
4. Existing tests still pass (`uv run pytest tests/`)
5. Linting passes (`uv run ruff check .`)

## Reference Files

Read these for context:
- `src/meridian/lib/launch/context.py` — current `prepare_launch_context()`
- `src/meridian/lib/launch/plan.py` — current bypass logic at lines 258-297
- `src/meridian/lib/launch/request.py` — SpawnRequest schema
- `src/meridian/lib/launch/policies.py` — resolve_policies
- `src/meridian/lib/launch/permissions.py` — resolve_permission_pipeline
- `src/meridian/lib/launch/run_inputs.py` — build_resolved_run_inputs
- `src/meridian/lib/launch/command.py` — spec/argv stages
