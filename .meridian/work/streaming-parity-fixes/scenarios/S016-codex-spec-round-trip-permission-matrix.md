# S016: Codex permission matrix semantics

- **Source:** design/edge-cases.md E16 + p1411 H1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester (+ @smoke-tester)
- **Status:** pending

## Given
Sandbox x approval matrix over:

- sandbox: `default`, `read-only`, `workspace-write`, `danger-full-access`
- approval: `default`, `auto`, `yolo`, `confirm`

## When
Matrix is projected for subprocess and streaming Codex paths.

## Then
- Semantic behavior and audit trail are distinct per mode intent.
- Wire strings may collapse where Codex exposes fewer knobs.
- No silent collapse to permissive behavior.

## Verification
- Parametrized tests assert semantic expectations per cell.
- Smoke subset validates representative runtime behavior.
- Audit logs confirm mode-specific handling (`auto` vs `yolo` vs `confirm`).

## Result (filled by tester)
_pending_
