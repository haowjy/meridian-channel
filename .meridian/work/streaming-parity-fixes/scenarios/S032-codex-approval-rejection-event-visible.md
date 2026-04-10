# S032: Codex approval rejection event visible on queue

- **Source:** design/edge-cases.md E32 + p1411 M9
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester (+ @smoke-tester)
- **Status:** pending

## Given
Streaming Codex in confirm mode receives `requestApproval`.

## When
Approval handler rejects request.

## Then
- Rejection event is enqueued first.
- Only after enqueue does handler await `send_error`.
- Ordering assertions use call sequence / sequence number, not wall-clock timing.

## Verification
- Unit test with instrumented queue/send_error hooks asserts enqueue-before-await.
- Smoke test verifies event appears before terminal failure signal.

## Result (filled by tester)
_pending_
