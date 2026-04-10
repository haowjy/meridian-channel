# S024: `LaunchContext` parity across runners

- **Source:** design/edge-cases.md E24 + p1411 finding M6
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A single `SpawnPlan` (canonical test fixture with all fields populated — env vars, cwd, harness, model, prompt, etc.).

## When
`prepare_launch_context(plan, ...)` is called twice with identical inputs.

## Then
- Both calls return `LaunchContext` instances that compare equal.
- Equality is structural: `.spec == .spec`, `.env == .env`, `.run_params == .run_params`, `.child_cwd == .child_cwd`, `.env_overrides == .env_overrides`.
- The helper is deterministic — no time-dependent, random, or PID-dependent fields leak into the context.
- Both runners (`runner.py` and `streaming_runner.py`) call the same `prepare_launch_context` helper; there is no parallel implementation.

## Verification
- Unit test: call `prepare_launch_context` twice, assert the results compare equal via `dataclasses.asdict` or explicit field-by-field.
- Unit test: invoke the helper through both runners' entrypoints (with stubbed subprocess launch) and assert both produce equal `LaunchContext` instances.
- Grep test (refactor check): `prepare_launch_context` has exactly one definition site.
- Test that re-calling the helper with a slightly different plan produces a different context (negative assertion).

## Result (filled by tester)
_pending_
