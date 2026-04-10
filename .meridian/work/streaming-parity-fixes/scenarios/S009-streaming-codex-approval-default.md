# S009: Streaming Codex with `approval=default`

- **Source:** design/edge-cases.md E9 + p1411 finding H1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
User spawns Codex streaming with `approval=default`. Real `codex app-server` is available.

## When
The streaming runner launches Codex.

## Then
- `codex app-server` launch command contains **no** `approval_policy` override. Codex applies its own default (accept-all in exec mode).
- No Meridian-side approval-accept logic runs (confirmed by debug trace showing no `requestApproval` entries from the Meridian handler).
- The spawn succeeds with the harness-native default behavior.
- Removing the override-suppression (making v2 behave like v1) causes this test to fail.

## Verification
- Run a streaming Codex spawn with `approval=default`.
- Inspect the debug trace: no `-c approval_policy=...` override in the launch command line.
- Inspect the Meridian handler log: no "auto-accepted approval" entries.
- Compare the launch command for `approval=default` vs `approval=auto` — they must differ in the presence/absence of the override.

## Result (filled by tester)
_pending_
