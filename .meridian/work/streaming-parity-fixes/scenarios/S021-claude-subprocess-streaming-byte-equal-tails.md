# S021: Claude subprocess vs streaming byte-equal arg tails

- **Source:** design/edge-cases.md E21 + p1411 finding M3
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A single canonical `ClaudeLaunchSpec` (same instance), and two base command prefixes:
- `SUBPROCESS_BASE = ("claude",)`
- `STREAMING_BASE = ("claude", "--output-format", "stream-json")` (or equivalent)

## When
`project_claude_spec_to_cli_args(spec, base)` is called with each base.

## Then
- `subprocess_args[:len(SUBPROCESS_BASE)] == SUBPROCESS_BASE`
- `streaming_args[:len(STREAMING_BASE)] == STREAMING_BASE`
- `subprocess_args[len(SUBPROCESS_BASE):] == streaming_args[len(STREAMING_BASE):]`
- The spec-derived tail is byte-equal regardless of base command.
- This property is the parity contract in executable form.

## Verification
- Unit test with the above assertions over the canonical spec.
- Property-based test (hypothesis-style): generate arbitrary valid `ClaudeLaunchSpec` instances and assert the byte-equal tail property holds for every sample.
- Any future change to the projection must maintain this test — it is the single most load-bearing test in the shared-projection promise.

## Result (filled by tester)
_pending_
