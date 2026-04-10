# S013: REST server POST with no permission block

- **Source:** design/edge-cases.md E13 + p1411 H3
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester (+ @unit-tester)
- **Status:** pending

## Given
REST server receives `/spawns` request with no permission metadata.

## When
Server resolves request permissions.

## Then
- Default mode returns `HTTP 400 Bad Request`.
- No implicit permission fallback is applied.
- Only with `--allow-unsafe-no-permissions` enabled does server construct `UnsafeNoOpPermissionResolver`.

## Verification
- Unit test default mode -> 400.
- Unit test opt-out mode -> resolver constructed + warning log.
- Grep confirms no `cast("PermissionResolver", None)` remains.

## Result (filled by tester)
_pending_
