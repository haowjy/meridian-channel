# Phase 5: Single-Owner Enforcement

## Scope

Rewire the driving adapters, executors, and driven adapters onto the new
factory seam so composition has one owner, fork materialization happens only
after a row exists, and session-id observation flows only through
`observe_session_id()`.

## Boundaries

- This phase is where the ownership rules become true in behavior, not just in
  architecture prose.
- Keep broad dead-type deletion and CI-gate replacement for Phase 6 so this
  phase can focus on behavior-preserving rewires and their tests.

## Touched Files and Modules

- Driving adapters:
  `src/meridian/lib/launch/plan.py`,
  `src/meridian/lib/launch/process.py`,
  `src/meridian/lib/ops/spawn/prepare.py`,
  `src/meridian/lib/ops/spawn/execute.py`,
  `src/meridian/lib/app/server.py`,
  `src/meridian/cli/streaming_serve.py`,
  `src/meridian/lib/streaming/spawn_manager.py`
- Single-owner modules:
  `src/meridian/lib/launch/fork.py`,
  `src/meridian/lib/launch/streaming_runner.py`
- Driven adapters:
  `src/meridian/lib/harness/claude.py`,
  `src/meridian/lib/harness/codex.py`,
  `src/meridian/lib/harness/opencode.py`
- Delete:
  `src/meridian/lib/launch/session_ids.py`
- New/updated tests:
  `tests/harness/test_observe_session_id.py`,
  `tests/ops/spawn/test_fork_after_row.py`,
  affected `tests/test_launch_process.py`,
  `tests/test_app_server.py`,
  `tests/exec/test_streaming_runner.py`,
  `tests/ops/test_spawn_prepare_fork.py`

## Claimed Leaf IDs

- `REQ-SC2`
- `REQ-SC5`
- `ARCH-I2`
- `ARCH-I3`
- `ARCH-I4`
- `ARCH-I10`
- `ARCH-I11`
- `ARCH-I12`

## Touched Refactor IDs

- `R06`

## Dependencies

- Phase 4

## Tester Lanes

- `@verifier`
- `@unit-tester`
- `@smoke-tester`

## Exit Criteria

- Driving adapters construct raw `SpawnRequest`/`LaunchRuntime`, call the
  factory, and do not call the prohibition-list composition helpers directly.
- Fork materialization has exactly one callsite and only runs after a spawn row
  exists in worker, primary, and app-streaming paths.
- `observe_session_id()` is implemented per adapter and is called exactly once
  post-execution by the driving adapter; inline scrape helpers are gone.
- `report.md` content extraction still yields user-facing report text across all
  supported harness families.
- `uv run ruff check .`
- `uv run pyright`
- Targeted pytest for fork ordering, lineage coherence, report content, and
  observation-path behavior
- Smoke coverage exercises the required launch lanes: streaming parity,
  primary lifecycle, dry-run/bypass, fork continuation, and adversarial state.

