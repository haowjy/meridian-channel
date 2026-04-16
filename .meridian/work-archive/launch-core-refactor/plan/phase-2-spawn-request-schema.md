# Phase 2: SpawnRequest Schema

## Scope

Make the raw persisted request artifact load-bearing. Define frozen,
JSON-round-trippable `SpawnRequest`, `SessionRequest`, `RetryPolicy`,
`ExecutionBudget`, and `LaunchRuntime` shapes, and move the prepare->execute
boundary onto that raw artifact without caching live resolver state.

## Boundaries

- No driver or executor rewire yet. Existing callers may still bridge through
  old composition paths while the raw schema lands.
- Do not move resolver/spec/argv construction into drivers while doing this.
  The only new durable artifact is the raw request.

## Touched Files and Modules

- `src/meridian/lib/harness/adapter.py`
- `src/meridian/lib/ops/spawn/plan.py`
- `src/meridian/lib/ops/spawn/prepare.py`
- `src/meridian/lib/ops/spawn/execute.py`
- Test fixtures currently constructing `PreparedSpawnPlan`
- New tests:
  `tests/launch/test_session_request_round_trip.py`
  and any fixture-transition tests needed for persisted artifacts

## Claimed Leaf IDs

- `REQ-SC3`
- `ARCH-I5`
- `FEAS-FV11`

## Touched Refactor IDs

- `R06`

## Dependencies

- Phase 1

## Tester Lanes

- `@verifier`
- `@unit-tester`
- `@smoke-tester`

## Exit Criteria

- `SpawnRequest` and its nested models round-trip through
  `model_dump_json` / `model_validate_json` with JSON-primitive fields only.
- No new or surviving persisted artifact in launch/spawn code requires
  `arbitrary_types_allowed = True`.
- Worker prepare persists a raw request artifact instead of a live-object-heavy
  pre-composed plan.
- Targeted tests cover the eight continuation fields and absence of serialized
  resolver/config sidechannels.
- `uv run ruff check .`
- `uv run pyright`
- Targeted pytest for new schema and prepare/execute artifact tests
- Smoke coverage proves prepare->execute still works from a clean temp state.

