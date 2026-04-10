# S028: Harness binary missing from PATH

- **Source:** design/edge-cases.md E28
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
Harness binary is unavailable on PATH.

## When
Spawn is launched via subprocess and streaming runners.

## Then
- Both runners surface structured `HarnessBinaryNotFound`.
- Error payload names missing binary and searched PATH.
- Error semantics are parity-aligned across runners.

## Verification
- Smoke matrix over harnesses and runner paths.
- Assert shared error class/shape and parity semantics.

## Result (filled by tester)
_pending_
