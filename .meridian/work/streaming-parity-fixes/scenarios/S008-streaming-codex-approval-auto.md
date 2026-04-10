# S008: Streaming Codex with `approval=auto`

- **Source:** design/edge-cases.md E8 + p1411 finding H1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
User spawns a Codex streaming task with `approval=auto`. Real `codex app-server` is available on PATH.

## When
Codex issues JSON-RPC `requestApproval` messages during the session.

## Then
- Every `requestApproval` is auto-accepted by the Meridian-side handler without prompting.
- The projection emits `-c approval_policy="auto"` (or the verified equivalent) so Codex itself knows the mode.
- Debug trace shows both the projection override AND the accept path on every approval call.
- No silent collapse to a generic "accept all" that loses the `auto` vs `yolo` vs `default` distinction.

## Verification
- Run a streaming Codex spawn that triggers at least one tool call requiring approval.
- Inspect debug.jsonl for the approval-accept entries and the launch-time `approval_policy` override.
- Confirm `approval=yolo` and `approval=auto` produce different wire commands (parametrized run).

## Result (filled by tester)
_pending_
