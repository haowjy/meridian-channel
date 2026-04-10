# S020: `continue_fork=True` with no `continue_session_id`

- **Source:** design/edge-cases.md E20
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Any launch-spec subclass is constructed with `continue_fork=True` and missing session id.

## When
Model validation runs.

## Then
- Construction raises `ValueError("continue_fork=True requires continue_session_id")`.
- Rule applies uniformly to Claude, Codex, and OpenCode via base-spec validator.

## Verification
- Parametrize over all three subclasses and assert same failure.
- Positive controls verify valid combinations still pass.

## Result (filled by tester)
_pending_
