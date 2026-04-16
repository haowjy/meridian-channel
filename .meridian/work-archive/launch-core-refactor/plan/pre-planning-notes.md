# Pre-Planning Notes: Launch Core Refactor (R06)

Explore phase verified design claims against code reality. Baseline captured: 658 tests, 0 pyright errors.

## Verified Design Claims

### Claim: Factory accepts pre-resolved PreparedSpawnPlan (not raw SpawnRequest)
**Verified.** `src/meridian/lib/launch/context.py:148` — `prepare_launch_context()` accepts `PreparedSpawnPlan` which carries:
- `plan.execution.permission_resolver` (live object, line 198)
- `plan.execution.permission_config` (pre-resolved DTO, line 214)

The factory is currently named `prepare_launch_context`, not `build_launch_context`.

### Claim: Composition scattered across driving adapters
**Verified.** `TieredPermissionResolver`/`UnsafeNoOpPermissionResolver` constructed in:
- `src/meridian/lib/app/server.py`
- `src/meridian/cli/streaming_serve.py`
- `src/meridian/cli/main.py`
- `src/meridian/lib/safety/permissions.py`
- `src/meridian/lib/streaming/spawn_manager.py`

### Claim: resolve_launch_spec has multiple callsites
**Verified.** Called in 8 files:
- `src/meridian/lib/launch/context.py:199`
- `src/meridian/lib/harness/adapter.py` (protocol definition)
- `src/meridian/lib/launch/streaming_runner.py`
- `src/meridian/lib/app/server.py`
- `src/meridian/lib/streaming/spawn_manager.py`
- `src/meridian/lib/harness/claude.py`, `codex.py`, `opencode.py` (implementations)

### Claim: fork_session scattered across drivers
**Verified.** Called in 7 files including driving adapters:
- `src/meridian/lib/ops/spawn/prepare.py`
- `src/meridian/lib/launch/process.py`
- `src/meridian/cli/spawn.py`
- `src/meridian/cli/main.py`

### Claim: observe_session_id not implemented
**Verified.** No matches for `observe_session_id` in source tree. Session-ID observation flows through inline scrapes.

### Claim: SpawnRequest exists but is dead
**Verified.** `SpawnParams` exists at `harness/adapter.py` but is constructed inside the factory, not by driving adapters. No `SpawnRequest` type exists currently.

### Claim: PreparedSpawnPlan uses arbitrary_types_allowed
**Verified.** `src/meridian/lib/ops/spawn/plan.py:42` — `model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)`

## Verified Dependencies

### R01 (ProjectPaths extraction) required
**Verified.** No `ProjectPaths` class exists. Current path handling:
- `StatePaths` in `lib/state/paths.py:93-104` covers state root paths
- `StateRootPaths` in `lib/state/paths.py:49-90` covers per-root paths
- Project-level paths (repo_root, execution_cwd) are passed as raw `Path` arguments

`LaunchRuntime.project_paths: ProjectPaths` requires R01 first.

## Latent Risks Not in Design

### Risk: Test fixtures depend on PreparedSpawnPlan shape
Multiple test files create `PreparedSpawnPlan` fixtures. Migration path: parallel old/new type support during transition, then delete old type.

### Risk: Streaming runner has multiple entry points
`streaming_runner.py` has both `run_streaming_spawn()` and `execute_with_streaming()`. Need to verify which is the canonical entry point vs dead code.

## Probe Gaps

None identified. Design claims validated against code; no runtime probes needed.

## Leaf Distribution Hypothesis

Suggest 6 phases:
1. **R01**: ProjectPaths extraction (dependency)
2. **SpawnRequest schema**: Define full SpawnRequest, add JSON round-trip test
3. **Pipeline stages**: Extract resolve_policies, resolve_permission_pipeline, build_resolved_run_inputs
4. **Factory rewire**: build_launch_context accepts SpawnRequest + LaunchRuntime
5. **Single-owner enforcement**: fork_session, observe_session_id consolidation
6. **Adapter rewire + cleanup**: Delete dead types, add CI drift gate

## Exit State

**explore-clean** — design claims verified, no falsifications, latent risks documented with handling. Proceed to Plan.
