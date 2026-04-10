# S022: User passes `--append-system-prompt` in `extra_args`

- **Source:** design/edge-cases.md E22 + p1411 M3
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
`ClaudeLaunchSpec` includes both Meridian-managed and user passthrough `--append-system-prompt` values.

## When
Claude projection runs.

## Then
- Both flags appear in output.
- Meridian-managed flag appears in canonical position.
- User passthrough copy appears later and wins by last-wins semantics.
- Warning log records known managed-flag collision.

## Verification
- Positional assertions for both flags.
- Caplog assertion for warning entry.
- Parity assertion across subprocess/streaming projections.

## Result (filled by tester)
_pending_
