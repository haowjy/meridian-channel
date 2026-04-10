# S020: `continue_fork=True` with no `continue_session_id`

- **Source:** design/edge-cases.md E20 (defensive; v1 silently ignored)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Caller constructs a `ClaudeLaunchSpec` with `continue_fork=True` and `continue_session_id=None`.

## When
The spec is constructed (or the adapter factory is called with equivalent `SpawnParams` fields).

## Then
- Construction raises `ValueError("continue_fork=True requires continue_session_id")`.
- No silent ignore. No launching a spawn that produces misleading behavior.
- The validation lives as a Pydantic model validator on `ClaudeLaunchSpec` so the constraint cannot be bypassed by constructing via a different path.

## Verification
- Unit test: `with pytest.raises(ValueError, match="continue_fork"): ClaudeLaunchSpec(continue_fork=True, continue_session_id=None, ...)`.
- Unit test: `continue_fork=True` with a real session id succeeds.
- Unit test: `continue_fork=False` with or without session id succeeds.
- Grep for any pre-v2 code path that swallowed this combination — must be removed.

## Result (filled by tester)
_pending_
