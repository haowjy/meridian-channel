# Phase 6: Adapter Cleanup And Drift Gate

## Scope

Delete the obsolete DTOs and heuristic guardrails, finish the adapter/driver
cleanup, and replace the old grep-based invariant check with behavioral factory
tests plus the reviewer-driven architectural drift gate.

## Boundaries

- This is the closeout phase. It should not invent new ownership rules; it
  should make the approved architecture enforceable and reviewable.
- Any test removals must be replaced in the same phase with equal or better
  coverage and called out explicitly in the execution report.

## Touched Files and Modules

- Delete:
  `src/meridian/lib/ops/spawn/plan.py`,
  `src/meridian/lib/launch/runner.py`,
  `scripts/check-launch-invariants.sh`
- Final cleanup for:
  `src/meridian/lib/harness/adapter.py`,
  `src/meridian/lib/launch/plan.py`,
  `src/meridian/lib/launch/process.py`,
  `src/meridian/lib/ops/spawn/prepare.py`,
  `src/meridian/lib/ops/spawn/execute.py`,
  `src/meridian/lib/app/server.py`,
  `src/meridian/cli/streaming_serve.py`
- New artifacts:
  `.meridian/invariants/launch-composition-invariant.md`,
  `.github/workflows/meridian-ci.yml`,
  `tests/launch/test_launch_factory.py`
- Optional lightweight CI-sanity test for the drift-gate wiring

## Claimed Leaf IDs

- `REQ-SC4`
- `REQ-SC6`
- `ARCH-I13`
- `FEAS-FV12`

## Touched Refactor IDs

- `R06`

## Dependencies

- Phase 5

## Tester Lanes

- `@verifier`
- `@unit-tester`
- `@smoke-tester`

## Exit Criteria

- `PreparedSpawnPlan`, `ExecutionPolicy`, top-level `SessionContinuation`,
  `ResolvedPrimaryLaunchPlan`, and the old launch invariant script are gone.
- `tests/launch/test_launch_factory.py` pins the required behavioral
  invariants, and the pytest count is not reduced net-of-replacements.
- CI runs the reviewer-based architectural drift gate on the protected launch
  surface and no longer depends on grep-count heuristics.
- Any adapter input transformations that remain surface through
  `LaunchContext.warnings` rather than silent mutation.
- `uv run ruff check .`
- `uv run pyright`
- Targeted pytest for final invariant coverage, plus the full relevant launch
  test slice
- Smoke coverage proves the shipped CLI paths still work end-to-end after the
  deletions and CI-gate swap.

