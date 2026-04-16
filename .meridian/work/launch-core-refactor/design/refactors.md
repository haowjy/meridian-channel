# Launch Core Refactor Agenda

This agenda covers the structural rearrangements needed to consolidate launch composition into a typed pipeline. The architecture is in `architecture/launch-core.md`; feasibility verdicts are in `feasibility.md`.

**Dependencies:**
- **R01 (ProjectPaths extraction):** `LaunchRuntime` carries `project_paths: ProjectPaths`, so R01 must land first.

## R06 — Consolidate launch composition into a typed pipeline (3 driving adapters → factory → 2 executors)

- **Type:** prep refactor

- **Why:** The first R06 implementation produced a hexagonal *shell* —
  `build_launch_context()` exists; `LaunchContext` is a sum type — but the
  *core* did not land. The factory accepts `PreparedSpawnPlan` whose
  `ExecutionPolicy` already carries resolved `PermissionConfig` and live
  `PermissionResolver` (`src/meridian/lib/ops/spawn/plan.py:9-21`). Every
  driving adapter must therefore call `resolve_policies` and
  `resolve_permission_pipeline` *before* it can construct factory input,
  which means composition still lives in drivers
  (`src/meridian/lib/launch/plan.py:234-334`,
  `src/meridian/lib/ops/spawn/prepare.py:202-328`,
  `src/meridian/lib/app/server.py:286-351`,
  `src/meridian/cli/streaming_serve.py:65`). The CI `rg`-count guards pass
  while the centralization invariant they were meant to protect is
  structurally false. The correctness review enumerated 14 concrete
  evasion patterns the script cannot catch.

  R06 is rewritten so the factory accepts raw `SpawnRequest` and runs an
  explicit named pipeline that owns every composition stage. Verification
  swaps from heuristic `rg` counts to a CI-spawned `@reviewer` architectural
  drift gate plus deterministic behavioral factory tests. The structural
  patterns (one builder per concern, driven port without mechanism leak,
  one fork owner, one bypass owner, one observation path) become honest
  through the type system and behavior, not through grep.

- **Scope (file list — not a how-to plan):**

  *Domain core:*
  - `src/meridian/lib/launch/context.py` — rewrite factory body to consume
    `SpawnRequest`; bypass branch becomes sole owner; remove pre-resolved
    `PreparedSpawnPlan` parameter.
  - `src/meridian/lib/launch/policies.py` — own `resolve_policies` definition.
  - `src/meridian/lib/launch/permissions.py` — own `resolve_permission_pipeline`.
  - `src/meridian/lib/launch/fork.py` — keep; single-owner enforced.
  - `src/meridian/lib/launch/env.py` — own `build_env_plan` as the sole env builder.
  - `src/meridian/lib/launch/command.py` — own `project_launch_command`; delete `build_launch_env`; remove bypass parsing.
  - `src/meridian/lib/launch/run_inputs.py` — new; owns `build_resolved_run_inputs`.
  - `src/meridian/lib/launch/runner.py` — delete.
  - `src/meridian/lib/launch/session_ids.py` — delete.
  - `src/meridian/lib/launch/__init__.py` — collapse dry-run preview duplication into the factory; primary entry calls factory.

  *Source extraction modules (current logic owners):*
  - `src/meridian/lib/launch/resolve.py` — policy resolution logic at lines 230-329 moves to `launch/policies.py`; remainder (config/profile/skill/model resolution helpers) stays.
  - `src/meridian/lib/safety/permissions.py` — permission pipeline construction logic at line 292 moves to `launch/permissions.py`; resolver class and lower-level helpers stay.

  *Driving adapters:*
  - `src/meridian/lib/launch/plan.py` — `resolve_primary_launch_plan` delegates composition to the factory; `ResolvedPrimaryLaunchPlan` is deleted.
  - `src/meridian/lib/launch/process.py` — consumes `LaunchContext`; stops calling `adapter.build_command` post-factory; no rebuild of `run_params` after planning.
  - `src/meridian/lib/ops/spawn/prepare.py` — `build_create_payload` constructs and persists `SpawnRequest`; no permission resolution; no fork materialization; no preview command construction outside the factory.
  - `src/meridian/lib/ops/spawn/execute.py` — reads persisted `SpawnRequest`, creates spawn row, calls factory; the independent `resolve_permission_pipeline()` call at line 861 is removed.
  - `src/meridian/lib/app/server.py` — constructs `SpawnRequest`, creates row, calls factory; no `TieredPermissionResolver` construction; no `adapter.resolve_launch_spec` direct call; uses exhaustive `match` over `LaunchContext`.
  - `src/meridian/cli/streaming_serve.py` — folds into shared `execute_with_streaming` path; constructs `SpawnRequest`; no hardcoded `TieredPermissionResolver(config=PermissionConfig())`.

  *Driven adapters:*
  - `src/meridian/lib/harness/adapter.py` — keep protocol contracts only; remove permission-flag projection logic; restore `SpawnRequest` to load-bearing.
  - `src/meridian/lib/harness/claude.py`, `harness/codex.py`, `harness/opencode.py` — each implements `observe_session_id()` (relocate existing scrape/connection logic). Permission-flag projection logic moves in from `adapter.py`.

  *Deletions:*
  - `src/meridian/lib/ops/spawn/plan.py` — `PreparedSpawnPlan`, `ExecutionPolicy`, `SessionContinuation` deleted; replaced by `SpawnRequest` + factory composition.
  - `src/meridian/lib/launch/streaming_runner.py:389` — `run_streaming_spawn` and its export deleted.
  - `src/meridian/lib/streaming/spawn_manager.py:180` — `SpawnManager.start_spawn` unsafe-resolver fallback deleted; `spec` parameter becomes required `LaunchContext`.
  - `scripts/check-launch-invariants.sh` — deleted.
  - `.github/workflows/meridian-ci.yml` — `check-launch-invariants` step removed; `architectural-drift-gate` step added.

  *New artifacts:*
  - `.meridian/invariants/launch-composition-invariant.md` — invariant prompt for the drift-gate reviewer.
  - `tests/launch/test_launch_factory.py` — behavioral factory tests.

- **Test blast radius** (enumerate before refactoring):
  ```
  rg -l "RuntimeContext|prepare_launch_context|LaunchContext|build_launch_context\
  |build_launch_env|build_harness_child_env|PreparedSpawnPlan|resolve_policies\
  |resolve_permission_pipeline|SpawnParams|merge_env_overrides\
  |resolve_launch_spec|run_streaming_spawn|SpawnRequest|materialize_fork\
  |ExecutionPolicy|SessionContinuation|ResolvedPrimaryLaunchPlan\
  |observe_session_id|extract_latest_session_id" tests/
  ```
  Known impacted test files include at minimum:
  - `tests/exec/test_streaming_runner.py`
  - `tests/exec/test_depth.py`
  - `tests/exec/test_permissions.py`
  - `tests/test_launch_process.py`
  - `tests/test_app_server.py`
  - `tests/ops/test_spawn_prepare_fork.py`
  - `tests/harness/test_codex_fork_session.py`
  - `tests/harness/test_launch_spec_parity.py` — verifies launch spec consistency across harnesses; affected by `resolve_launch_spec_stage` extraction

  Tests added by R06:
  - `tests/launch/test_launch_factory.py` (the verification-layer 1 suite enumerated below)
  - `tests/launch/test_session_request_round_trip.py` — `SpawnRequest` JSON round-trip without `arbitrary_types_allowed`
  - `tests/harness/test_observe_session_id.py` — per-adapter observation contract
  - `tests/ops/spawn/test_fork_after_row.py` — worker ordering
  - `tests/cli/test_invariants_drift_gate.py` (optional, lightweight) — sanity check that the invariant prompt and CI step exist

  All identified tests must be updated in the same change set as the source
  refactor, not left as follow-up drift.

- **Suggested internal phasing** (the planner can rearrange; this is one
  honest sequencing):

  1. Make `SpawnRequest` load-bearing: define the full schema (currently
     dead at `harness/adapter.py:150`); add JSON round-trip test. No
     callers yet.
  2. Pipeline stage extraction: move `resolve_policies` into
     `launch/policies.py`, `resolve_permission_pipeline` into
     `launch/permissions.py`, `project_launch_command` into
     `launch/command.py`. Add behavioral factory test scaffolding.
  3. `build_resolved_run_inputs` aggregator + factory-internal
     `ResolvedRunInputs` rename.
  4. `build_launch_context` accepts `SpawnRequest` + `LaunchRuntime`;
     bypass branch becomes sole owner; preflight runs inside bypass for
     dry-run parity.
  5. `materialize_fork` single-owner enforcement (delete `prepare.py`
     inline copy); fork-after-row ordering tests.
  6. `observe_session_id` per-adapter implementations + executor
     `LaunchOutcome` return + driving-adapter assembly of `LaunchResult`.
     Delete `launch/session_ids.py`.
  7. Rewire each driving adapter: primary, then worker, then app streaming.
     Each transition a separate commit; behavioral tests gate.
  8. Delete `PreparedSpawnPlan`, `ExecutionPolicy`, `SessionContinuation`
     (top-level), `ResolvedPrimaryLaunchPlan`. Type ladder collapses.
  9. Delete `scripts/check-launch-invariants.sh`; add invariant prompt at
     `.meridian/invariants/launch-composition-invariant.md`; rewire CI.
  10. Driven port cleanup: move permission-flag projection out of
      `harness/adapter.py` into adapters.
  11. `RuntimeContext` unification (one type in `core/context.py`).

  Steps 1–3 land independently. Step 4 unblocks 5/6. Steps 7 land per
  driver and are gated by behavioral tests. Step 8 closes the type
  collapse. Steps 9–11 are cleanup that can land in parallel with each
  other but after the rewires complete.

- **Exit criteria:**
  - `build_launch_context()` accepts raw `SpawnRequest` + `LaunchRuntime`; no pre-resolved `PreparedSpawnPlan`.
  - Driving adapters contain zero calls to the prohibition list.
  - `SpawnRequest` round-trips via `model_dump_json` / `model_validate_json` without escape hatches.
  - Behavioral factory tests in `tests/launch/test_launch_factory.py` pass.
  - CI architectural drift gate operational.
  - `scripts/check-launch-invariants.sh` deleted.

## Verification

`scripts/check-launch-invariants.sh` is **deleted** in this refactor. The
`check-launch-invariants` step is removed from
`.github/workflows/meridian-ci.yml`. Verification is three layers:

**1. Behavioral factory tests** (`tests/launch/test_launch_factory.py`,
new) — pin the load-bearing invariants directly. Required tests:

- `test_factory_resolves_permissions_from_raw_inputs` — given a
  `SpawnRequest` with sandbox/approval/allowed/disallowed_tools, the
  returned `NormalLaunchContext.perms` reflects the policy. **Asserts a
  driver does not need to construct any `PermissionResolver` to call the
  factory.**
- `test_factory_dry_run_argv_matches_runtime_argv` — for the same
  `SpawnRequest`, `dry_run=True` and `dry_run=False` produce identical
  argv (preflight runs in both paths).
- `test_factory_dry_run_skips_fork_materialization` — given a request
  that would normally fork, `dry_run=True` returns context with original
  session id and no `fork_session()` call (mock the adapter and assert).
- `test_factory_bypass_dispatch_single_owner` — when
  `MERIDIAN_HARNESS_COMMAND` is set in `runtime`, the factory returns
  `BypassLaunchContext` with preflight-expanded passthrough args
  included in `argv`.
- `test_factory_returns_normal_context_with_required_fields` —
  `NormalLaunchContext` fields are all required at construction
  (frozen, no `None` defaults on load-bearing fields).
- `test_observe_session_id_dispatched_through_adapter` — given a fake
  adapter that records `observe_session_id` calls, assert it is called
  exactly once after the executor returns `LaunchOutcome`, and the
  returned `LaunchResult.session_id` equals what the adapter returned.
- `test_fork_after_spawn_row_in_worker` — wire a fake spawn-store +
  fake adapter; assert `start_spawn` returns before `fork_session` is
  invoked when worker `execute.py` calls the factory.
- `test_streaming_runner_requires_spawn_row_precondition` — calling
  `execute_with_streaming` without a created spawn row raises a
  precondition error before any factory work runs.
- `test_persisted_spawn_request_round_trips` — `SpawnRequest` →
  `model_dump_json` → `model_validate_json` produces an equal value
  with no live-object fields.
- `test_no_pre_resolved_permission_resolver_in_persisted_artifact` —
  inspect the JSON form of a persisted `SpawnRequest`; assert no field
  name carries a serialized resolver/config blob.
- `test_child_cwd_not_created_before_spawn_row` — wire a fake spawn-store and a temp-dir fake `child_cwd`
  helper; assert `start_spawn` returns before `mkdir`/`resolve_child_execution_cwd`
  is invoked when any driver path reaches the factory.
- `test_composition_warnings_propagate_to_launch_context` — register a
  pipeline stage that appends a `CompositionWarning`; assert the
  returned `NormalLaunchContext.warnings` contains it in order.
- `test_workspace_projection_seam_reachable` — register a fake adapter whose `project_workspace()` returns a
  sentinel `extra_args` value; assert the resulting argv contains the
  sentinel after `build_launch_argv()`.
- `test_unsafe_no_permissions_dispatches_through_factory` — set
  `runtime.unsafe_no_permissions = True`; assert
  `NormalLaunchContext.perms` is an `UnsafeNoOpPermissionResolver`
  instance and the driving adapter never called the resolver
  constructor itself.
- `test_session_request_carries_all_eight_continuation_fields` —
  given a `SessionRequest` with all eight fields populated,
  round-trip through `SpawnRequest.model_dump_json` /
  `model_validate_json`; assert no field is lost.
- `test_fork_produces_consistent_lineage_across_jsonl_stores` — fork a spawn; assert the new
  `sessions.jsonl` chat row's id matches the new `spawns.jsonl` start
  row's `chat_id`.
- `test_fork_start_row_omits_harness_session_id` — inspect the first `start` event written for a
  forked child's spawn row; assert `harness_session_id` is absent.
- `test_report_content_contract_across_harnesses` — run a successful spawn on each of claude, codex,
  opencode; assert `report.md` starts with the agent's text content
  and contains no transport-event markers.
- `test_workspace_projection_produces_semantically_correct_argv` — assert the projected argv is
  semantically correct for the target harness.

**2. CI-spawned `@reviewer` as architectural drift gate.** A new file
`.meridian/invariants/launch-composition-invariant.md` declares the
semantic invariants in prose. A new step in
`.github/workflows/meridian-ci.yml` runs only on PRs that touch files
under `src/meridian/lib/(launch|harness|ops/spawn|app)/`.

**3. pyright + ruff + pytest** remain the correctness gate. The
drift-gate reviewer sits beside them, not in place of them.

## Plan-Level Constraints

Driven by R06-v1 smoke evidence:

- Net pytest count must be non-negative across the whole R06 series.
  Phases that remove tests require an explicit decision-log entry
  naming the replacement coverage.
- Per-phase smoke lane in addition to per-phase unit tests. Use the
  5-lane pattern (streaming-parity, primary-lifecycle, dry-run-bypass,
  fork-continuation, adversarial-state).
- Pre-implementation smoke baseline required before Phase 1 coder opens.
- Implementation MUST run against meridian-cli ≥ v0.0.30 (post-Fix-A).

## Out of Scope

- GitHub issue #34 — Popen-fallback session-ID observability via
  filesystem polling. R06 lands the `observe_session_id()` adapter seam;
  the mechanism swap to filesystem polling is a separate change.
- Claude session-accessibility symlinking.
- Removing dead legacy subprocess-runner code (issue #32).
- Per-harness workspace projection mechanics (separate work item).
- Config file relocation (R01/R02, separate work item).
