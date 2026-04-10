# S032: Codex approval rejection event visible on queue

- **Source:** design/edge-cases.md E32 + p1411 finding M9
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester (+ @smoke-tester)
- **Status:** pending

## Given
A streaming Codex spawn configured with `approval=confirm` and no interactive channel. A consumer is subscribed to the event queue emitted by `CodexConnection`.

## When
A `requestApproval` JSON-RPC frame arrives on the codex_ws channel.

## Then
- The connection emits `HarnessEvent(kind="warning/approvalRejected", data={"reason": "confirm_mode", "method": method, "request_id": id})` to the event queue.
- The event appears **before** the JSON-RPC error response is sent back to Codex.
- The consumer observes the event directly, without having to infer rejection from a downstream turn failure.
- Event ordering is deterministic: event emission happens synchronously before the error response write.

## Verification
- Unit test: drive `codex_ws` approval handler directly with a synthetic `requestApproval` frame; capture the event queue via a fake subscriber; assert the `warning/approvalRejected` event is enqueued.
- Unit test: assert ordering — the event timestamp (or sequence number) precedes the JSON-RPC error response.
- Smoke test (pairs with S010): run a real Codex spawn, observe the event stream, assert the event appears before any session-failed event.
- Negative test: without the fix (v1 log-only behavior), the test fails because no event is produced.

## Result (filled by tester)
_pending_
