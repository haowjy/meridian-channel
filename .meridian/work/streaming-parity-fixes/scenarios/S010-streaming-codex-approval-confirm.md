# S010: Streaming Codex with `approval=confirm` rejects and emits event

- **Source:** design/edge-cases.md E10 + p1411 finding H1 + M9
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester (+ @unit-tester for queue assertion)
- **Status:** pending

## Given
User spawns Codex streaming with `approval=confirm`. There is no interactive channel attached. Real `codex app-server` is available.

## When
Codex issues a JSON-RPC `requestApproval` during the session.

## Then
- Meridian rejects the approval request (returns a JSON-RPC error back to Codex).
- **Before** the JSON-RPC error response is sent, a `HarnessEvent("warning/approvalRejected", {"reason": "confirm_mode", "method": method})` is enqueued on the event stream.
- A warning is logged.
- The consumer observing the event queue sees the rejection event directly without having to infer from downstream turn failures.

## Verification
- Unit test: drive the `codex_ws` approval handler with a synthetic `requestApproval` frame and assert the event queue has the `warning/approvalRejected` event.
- Smoke test: run a real `approval=confirm` spawn that forces a tool call, capture the event stream, assert the warning event is present and appears before the final error.
- Confirm v1 behavior (log-only, no event) is now impossible — grep the handler for the log statement and ensure the event emission sits next to it.

## Result (filled by tester)
_pending_
