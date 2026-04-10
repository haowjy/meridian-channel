# S023: `--allowedTools` merged from resolver + extra_args

- **Source:** design/edge-cases.md E23 + p1411 finding H2
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `ClaudeLaunchSpec` where:
- `permission_resolver` emits `--allowedTools A,B` via `resolve_flags`
- `extra_args = ("--allowedTools", "C,D")`

## When
`project_claude_spec_to_cli_args` runs.

## Then
- The final command contains exactly **one** `--allowedTools` flag.
- Its value is the deduped union `A,B,C,D` in positional order.
- The flag sits at the canonical position for permissions (after `--agents`/`--resume`/`--fork-session`, before any other extra args).
- Other values in `extra_args` (not `--allowedTools`) flow through unchanged.

## Verification
- Unit test: construct the inputs, call the projection, assert `list.count("--allowedTools") == 1`.
- Unit test: assert the value string is exactly `"A,B,C,D"` (order matters — A,B from resolver before C,D from extra_args).
- Unit test: confirm a different `extra_args` (e.g., `("--foo","bar","--allowedTools","C,D")`) still dedupes correctly and the `--foo bar` is preserved.
- Parity test: subprocess and streaming produce identical output for this scenario.

## Result (filled by tester)
_pending_
