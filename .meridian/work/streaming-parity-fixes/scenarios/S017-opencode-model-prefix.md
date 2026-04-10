# S017: OpenCode spec with `opencode-` model prefix

- **Source:** design/edge-cases.md E17 (inherited v1 D3 constraint)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Caller sets `model="opencode-claude-3-5-sonnet"` on a spawn routed to the OpenCode adapter.

## When
`OpenCodeAdapter.resolve_launch_spec(params, perms)` constructs the `OpenCodeLaunchSpec`.

## Then
- The factory strips the leading `opencode-` prefix exactly once, producing `model="claude-3-5-sonnet"` on the spec.
- Subprocess path sends `--model claude-3-5-sonnet` on the CLI.
- Streaming path sends `claude-3-5-sonnet` in the HTTP session payload to `opencode serve`.
- No double-strip (repeated invocation does not further mutate the string).
- No lingering `opencode-` prefix reaches the wire.

## Verification
- Unit test: call the factory with `model="opencode-claude-3-5-sonnet"`, assert `spec.model == "claude-3-5-sonnet"`.
- Unit test: call the factory with `model="claude-3-5-sonnet"`, assert `spec.model == "claude-3-5-sonnet"` (no-op for already-stripped).
- Unit test: assert the subprocess projection passes the stripped value to `--model`.
- Unit test: assert the streaming projection passes the stripped value in the HTTP payload.

## Result (filled by tester)
_pending_
