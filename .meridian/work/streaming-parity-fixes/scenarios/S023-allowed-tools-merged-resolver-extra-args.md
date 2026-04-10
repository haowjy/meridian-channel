# S023: `--allowedTools` from resolver and user `extra_args` both forwarded verbatim

- **Source:** design/edge-cases.md E23 + p1411 finding H2 + revision round 3 reframe (D1)
- **Added by:** @design-orchestrator (design phase)
- **Updated by:** @design-orchestrator (revision round 3)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `ClaudeLaunchSpec` where:
- `permission_resolver` emits `--allowedTools A,B` via `resolve_flags()` (resolver-internal merge of multiple sources)
- `extra_args = ("--allowedTools", "C,D")`

## When
`project_claude_spec_to_cli_args(spec)` runs.

## Then
- The resolver-derived `--allowedTools A,B` appears in canonical position (the Meridian-managed permission section).
- The user's `--allowedTools C,D` appears verbatim in the passthrough tail, unchanged.
- Both flags are present in the final command line.
- Meridian does **not** merge, dedupe, or strip across the resolver/`extra_args` boundary.
- A debug log records the collision ("known managed flag `--allowedTools` also present in extra_args; user value wins by last-wins semantics").
- Other values in `extra_args` (not `--allowedTools`) flow through unchanged.

## Verification
- Unit test: construct the inputs, call the projection, assert `list.count("--allowedTools") == 2`.
- Unit test: assert the ordering is "resolver first, user `extra_args` second" so Claude's last-wins flag handling picks the user value.
- Unit test: confirm a different `extra_args` (e.g., `("--foo","bar","--allowedTools","C,D")`) preserves `--foo bar` verbatim in the tail.
- Parity test: subprocess and streaming produce identical tails for this scenario.
- Caplog assertion for the debug collision log.

## Result (filled by tester)
_pending_
