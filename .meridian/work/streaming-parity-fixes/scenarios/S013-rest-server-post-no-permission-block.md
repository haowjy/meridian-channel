# S013: REST server POST with no permission block

- **Source:** design/edge-cases.md E13 + p1411 finding H3 + L6
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester (+ @unit-tester)
- **Status:** pending

## Given
The Meridian REST server is running. A client POSTs `/spawns` with a body that contains no permission metadata. Server is configured in lenient default mode.

## When
The server handler in `server.py` constructs the spawn params and routes them to the adapter's `resolve_launch_spec`.

## Then
- The handler constructs a real `NoOpPermissionResolver()` instance (not `cast("PermissionResolver", None)`).
- A warning log is emitted at the moment of construction: "No permission block supplied; using NoOpPermissionResolver (no enforcement)".
- The spawn runs to completion without permission enforcement.
- Grep across the tree shows zero `cast("PermissionResolver", None)` matches.

## Verification
- Unit test: import `server.py` handler, build a fake request with no permission block, assert a `NoOpPermissionResolver` instance is constructed and a warning is logged.
- Smoke test: POST a real spawn request without permissions to a running server and observe the warning in the server log; confirm the spawn runs.
- `rg "cast\\(.*PermissionResolver" src/` returns zero.
- Confirm `NoOpPermissionResolver.__init__` logs a warning (not just the call site).

## Result (filled by tester)
_pending_
