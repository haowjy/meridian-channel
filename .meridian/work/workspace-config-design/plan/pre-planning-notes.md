# R06 Pre-Planning Notes (Fresh Explore Phase)

Explore phase owner: impl-orchestrator p1941.
Input design: convergence-3 `ready-with-minor-followups` + architect closure.
Target: R06 — Consolidate launch composition into a typed pipeline.

## Verified design claims

### Driving-adapter prohibition violations (I-2) — matches design exactly

All expected violations confirmed at claimed line numbers against HEAD:

| File | Line | Symbol |
|---|---|---|
| `src/meridian/lib/launch/plan.py` | 17 | `import resolve_permission_pipeline` |
| `src/meridian/lib/launch/plan.py` | 25 | `import resolve_policies` |
| `src/meridian/lib/launch/plan.py` | 234 | `policies = resolve_policies(...)` |
| `src/meridian/lib/launch/plan.py` | 312 | `adapter.seed_session(...)` |
| `src/meridian/lib/launch/plan.py` | 329 | `resolve_permission_pipeline(...)` |
| `src/meridian/lib/launch/plan.py` | 349 | `adapter.filter_launch_content(...)` |
| `src/meridian/lib/launch/plan.py` | 383 | `adapter.build_command(...)` |
| `src/meridian/lib/launch/process.py` | 44 | `import extract_latest_session_id` |
| `src/meridian/lib/launch/process.py` | 454 | `extract_latest_session_id(...)` |
| `src/meridian/lib/ops/spawn/prepare.py` | 25 | `import resolve_policies` |
| `src/meridian/lib/ops/spawn/prepare.py` | 31 | `import resolve_permission_pipeline` |
| `src/meridian/lib/ops/spawn/prepare.py` | 202 | `resolve_policies(...)` |
| `src/meridian/lib/ops/spawn/prepare.py` | 302-305 | `fork_session(...)` via `getattr` |
| `src/meridian/lib/ops/spawn/prepare.py` | 323 | `resolve_permission_pipeline(...)` |
| `src/meridian/lib/app/server.py` | 27-28 | imports `TieredPermissionResolver`, `UnsafeNoOpPermissionResolver` |
| `src/meridian/lib/app/server.py` | 300 | `UnsafeNoOpPermissionResolver()` |
| `src/meridian/lib/app/server.py` | 319 | `TieredPermissionResolver(config=...)` |
| `src/meridian/cli/streaming_serve.py` | 14 | `import resolve_permission_pipeline` |
| `src/meridian/cli/streaming_serve.py` | 65 | `resolve_permission_pipeline(...)` |
| `src/meridian/lib/launch/streaming_runner.py` | 44 | `import build_launch_context` |
| `src/meridian/lib/launch/streaming_runner.py` | 71 | `import extract_latest_session_id` |
| `src/meridian/lib/launch/streaming_runner.py` | 637 | `build_launch_context(...)` |
| `src/meridian/lib/launch/streaming_runner.py` | 694 | `spawn_store.start_spawn(...)` |
| `src/meridian/lib/launch/streaming_runner.py` | 860 | `extract_latest_session_id(...)` |

`ops/spawn/execute.py` has NO `resolve_permission_pipeline` or `TieredPermissionResolver` call. The design's reference to `execute.py:861 resolve_permission_pipeline` is stale — the current execute.py no longer holds that call; composition for the worker runs through `prepare.py` today, and execute.py dispatches to `execute_with_streaming` via `streaming_runner.py`. **No missed violation sites**; the design's prohibition list holds against current code.

### Fork-after-row ordering (I-10)

- **Primary** (`launch/process.py`): line 306 creates row, line 328 calls factory — ordering holds. ✓
- **Streaming-runner fallback** (`launch/streaming_runner.py`): line 637 builds context, line 694 start_spawn — ordering **violated** (current). This is the D7 correctness issue the redesign identified; R06 must enforce `start_spawn`-before-`build_launch_context` here.
- **Current factory internal** (`launch/context.py:111-117`): child_cwd is created inside factory using passed `spawn_id`. The factory depends on the caller to have created the row first — no intrinsic enforcement. R06 must make this a precondition by narrowing the child-cwd helper signature or asserting in the factory.

### Current `build_launch_context` signature

```python
def build_launch_context(
    *,
    spawn_id: str,
    run_prompt: str,
    run_model: str | None,
    plan: PreparedSpawnPlan,  # ← pre-resolved: carries ExecutionPolicy
                              #   → PermissionConfig + live PermissionResolver
    harness: SubprocessHarness,
    execution_cwd: Path,
    state_root: Path,
    plan_overrides: Mapping[str, str],
    report_output_path: Path,
    runtime_work_id: str | None = None,
    runtime_chat_id: str | None = None,
    runtime_spawn_id: str | None = None,
    harness_command_override: str | None = None,
) -> LaunchContext: ...
```

This is exactly what D19 flagged. Factory downstream of composition; driving adapters must compose `PreparedSpawnPlan` before calling. Target shape is
`build_launch_context(SpawnRequest, LaunchRuntime, *, dry_run: bool)`.

### `NormalLaunchContext` current shape (`launch/context.py:31-42`)

```python
@dataclass(frozen=True)
class NormalLaunchContext:
    run_params: SpawnParams
    perms: PermissionResolver
    spec: ResolvedLaunchSpec
    child_cwd: Path
    env: Mapping[str, str]
    env_overrides: Mapping[str, str]
    report_output_path: Path
```

Missing from target shape:

- `argv: tuple[str, ...]` — explicit argv (today executors call `adapter.build_command` again post-factory, which is part of the split-callsite violation).
- `harness_adapter` ref — executors currently rely on closure; target shape makes it explicit so the driving adapter can call `observe_session_id` on the same adapter instance.
- `warnings: tuple[CompositionWarning, ...]` — composition-warning sidechannel replacing deleted `PreparedSpawnPlan.warning`.

`BypassLaunchContext` is missing `warnings` as well. R06 must add it per D20.3.

`env_overrides` is today retained because executor merges it with preflight env at runtime. Post-R06 the factory produces the final `env` and `env_overrides` may be redundant; planner should decide whether to keep as an observation field or remove.

### `LaunchRuntime` field completeness

Walking the live drivers for runtime-injected (non-user-input) fields:

| Field (design) | Current source |
|---|---|
| `launch_mode: Literal["primary","background"]` | `SpawnParams.interactive: bool` today — true for primary, false otherwise |
| `unsafe_no_permissions: bool` | `app/server.py:300` driver-side branch on CLI flag |
| `debug: bool` | `BackgroundWorkerParams.debug` (`execute.py:103`) and payload.debug propagation |
| `harness_command_override: str \| None` | `MERIDIAN_HARNESS_COMMAND` env, today read by factory directly (no driver injection) |
| `report_output_path: str \| None` | Varies per driver; resolved from spawn artifacts dir |
| `state_paths: StatePaths` | `resolve_state_paths(repo_root)` call at multiple sites |
| `project_paths: ProjectPaths` | Not yet introduced — introduced by R01 (not a dep of R06; R06 can take a minimal placeholder or skip wiring project_paths until R01 lands) |

**Decision:** R06 should ship `LaunchRuntime` without `project_paths` until R01 introduces `ProjectPaths`, OR accept a forward-compatible placeholder shape. Planner must choose. Recommended: include `project_paths: ProjectPaths` if R01 has already landed on main; otherwise omit and note the R01-follow-up insertion point.

**Verified: R01 not yet landed on main** — `rg ProjectPaths src/` returns no results. R06 ships `LaunchRuntime` without `project_paths`; R01 adds it later.

Candidate additional fields walked and rejected:
- `runtime_work_id`, `runtime_chat_id`, `runtime_spawn_id` — these are `RuntimeContext` fields (read from env via `RuntimeContext.from_environment()`), not driver-injected. D17 calls for `RuntimeContext` unification in `core/context.py`; no need to put them on `LaunchRuntime`.
- Control-socket handles (`app/server.py` SpawnManager) — manager lifecycle is owned by the driving adapter; does not need to reach the factory.
- Telemetry/span context — not load-bearing for launch composition.

No missing fields identified. `LaunchRuntime` field set as designed is complete.

### A04 observe-session-id wording — architect closure verified

`design/architecture/harness-integration.md:152-154` reads:

> `observe_session_id()` reads per-launch inputs only — either parsed from `launch_outcome.captured_stdout` (for harnesses whose executor's PTY mode populated it) or read from per-launch state reachable via `launch_context`.

Unified contract in place. Convergence-3 major ("A04 still carries pre-D20 'getter not parser' language") is closed.

### FV-11 worker re-resolution semantics (spot check)

Today's `execute.py` does not re-run `resolve_permission_pipeline` (grep confirms no call). The composition is persisted in the `PreparedSpawnPlan` JSON blob via `arbitrary_types_allowed=True` on `PermissionResolver` fields — the live object ships through the spawn row/payload. R06's simplification (re-run the factory inside execute with the persisted `SpawnRequest`) is a strict improvement over today's serialization hack; it also closes the `disallowed_tools` correctness gap mentioned in `refactors.md` red-flag.

Declared behavior-preserving per D20. No probe needed — the re-composition is simpler than today's serialization of live objects.

### Incidental inconsistency (convergence-3 minor)

`report_output_path` spelling:

- `refactors.md:318` — `report_output_path: Path`
- `launch-core.md:167` — `report_output_path: str \| None`

Invariant I-5 forbids `Path` on persisted DTOs; `LaunchRuntime` is NOT persisted (per `refactors.md:323-324`), so either spelling is admissible. **Planner decision:** use `str | None` uniformly across the factory boundary to match the persistence-friendly pattern used by `SpawnRequest`; document the choice in `decisions.md` as a caveat.

Similarly convergence-3's `LaunchRuntime` pydantic-vs-dataclass caveat: **use pydantic frozen BaseModel** (matches every other factory-boundary DTO).

## Falsified design claims

None. Every structural claim in `refactors.md` R06 and `launch-core.md` A06 that was checkable at Explore altitude matches the current source code.

## Latent risks

1. **Fork-after-row in streaming fallback (`streaming_runner.py:637` before `:694`)** — design requires this become a fail-fast precondition error. Implementation must change `execute_with_streaming` to require the row exists before any factory work; the fallback path that creates rows mid-flight must be removed. Pin with `test_streaming_runner_requires_spawn_row_precondition`.

2. **Three `resolve_child_execution_cwd` callsites in execute.py (lines 429, 513, 699)** — current helper is callable pre-row. R06 must narrow the helper so `mkdir` requires an existing spawn row. Pin with `test_child_cwd_not_created_before_spawn_row`.

3. **`SpawnParams.interactive: bool` is load-bearing across driven adapters** — every adapter branches on `interactive` to decide argv flags (`--print`, `--resume`, session format). The rename to `LaunchRuntime.launch_mode: Literal["primary","background"]` plus each driven adapter reading `launch_mode` through whatever shape the factory passes downstream needs careful touching; risk of missing a driven-adapter branch. Map every `SpawnParams.interactive` read during phase 1.

4. **`RuntimeContext` duplicate type** — `launch/context.py:42` (historically) plus `core/context.py:13`. D17 and R06 scope include unification. The `launch/context.py` in-tree today imports from `core.context` (line 13), so the duplicate may already be resolved. Planner should re-verify as phase 0 or fold into phase 1.

5. **`build_launch_context` currently handles `harness_command_override` via kwarg** — factory already owns bypass. But preview path in `launch/__init__.py:65-77` and parse in `launch/command.py:53` are potential duplicates per design. Need to verify whether the duplicates still exist on HEAD; earlier commits landed a partial bypass-consolidation (D17-ish).

6. **Background worker `disallowed_tools` red flag** — R06 scope leaves this fix as its own commit. Do NOT fix in R06 phases; do NOT skip adding the field to `SpawnRequest` schema. Post-R06 follow-up work item.

## Probe gaps

None that block planning. Launch composition is all code-visible; no runtime probe needed beyond verification already done.

## Leaf-distribution hypothesis

Spec leaves are not changing (R06 is structural; no user-facing EARS contracts move). But 15 behavioral tests from `refactors.md` R06 verification map to implementation phases:

| Test | Phase ownership |
|---|---|
| `test_factory_resolves_permissions_from_raw_inputs` | Phase 2 (pipeline stage extraction) or Phase 4 (factory accepts raw input) |
| `test_factory_dry_run_argv_matches_runtime_argv` | Phase 4 |
| `test_factory_dry_run_skips_fork_materialization` | Phase 5 |
| `test_factory_bypass_dispatch_single_owner` | Phase 4 (bypass becomes sole owner) |
| `test_factory_returns_normal_context_with_required_fields` | Phase 4 |
| `test_observe_session_id_dispatched_through_adapter` | Phase 6 |
| `test_fork_after_spawn_row_in_worker` | Phase 5 or Phase 7 (worker rewire) |
| `test_streaming_runner_requires_spawn_row_precondition` | Phase 5 |
| `test_persisted_spawn_request_round_trips` | Phase 1 |
| `test_no_pre_resolved_permission_resolver_in_persisted_artifact` | Phase 1 (schema), verified against Phase 7 (worker rewire) |
| `test_child_cwd_not_created_before_spawn_row` | Phase 5 |
| `test_composition_warnings_propagate_to_launch_context` | Phase 4 (shape) + Phase 7 (driver surfacing) |
| `test_workspace_projection_seam_reachable` | Phase 2 (stage split in command.py) |
| `test_unsafe_no_permissions_dispatches_through_factory` | Phase 2 (permissions stage owns dispatch) |
| `test_session_request_carries_all_eight_continuation_fields` | Phase 1 |

Phase sequencing (follows `refactors.md` suggested 11-step breakdown, compressed for planner to refine):

1. Define `SpawnRequest` + nested models + `LaunchRuntime` + `CompositionWarning`; JSON round-trip tests.
2. Pipeline stage extraction: `policies.py`, `permissions.py`, `command.py` split (spec / projection / argv), `run_inputs.py` new, `fork.py` kept, `env.py` owns `build_env_plan`. Behavioral test scaffolding.
3. Factory rewrites to `(SpawnRequest, LaunchRuntime, *, dry_run)`; bypass becomes sole owner inside factory; `NormalLaunchContext.argv`/`warnings` added; `LaunchContext.warnings` channel.
4. `materialize_fork` single-owner enforcement (delete inline copy in `prepare.py`); fork-after-row preconditions; child-cwd helper signature narrowing.
5. Per-adapter `observe_session_id`; executor `LaunchOutcome` return; driving-adapter `LaunchResult` assembly; delete `session_ids.py`.
6. Rewire drivers: primary (`launch/plan.py`, `launch/process.py`), worker (`ops/spawn/prepare.py`, `execute.py`), app streaming (`app/server.py`). Delete `cli/streaming_serve.py` driver (folded into app-streaming).
7. Delete `PreparedSpawnPlan`, `ExecutionPolicy`, top-level `SessionContinuation`, `ResolvedPrimaryLaunchPlan`, user-facing `SpawnParams`.
8. Driven port cleanup: move permission-flag projection out of `harness/adapter.py` into adapters; driven-port contracts-only.
9. Delete `scripts/check-launch-invariants.sh` + CI step; copy invariant prompt to `.meridian/invariants/launch-composition-invariant.md`; add `@reviewer` CI step.
10. `RuntimeContext` unification (one type in `core/context.py`) if duplicate still present.

Phases are largely linear with narrow parallelism windows. Planner owns final decomposition.

## Exit state: **explore-clean**

All design claims verified against code reality. One convergence-3 minor (report_output_path spelling) resolved via convention choice; no redesign trigger. Proceeding to plan.
