# S022: User passes `--append-system-prompt` in `extra_args`

- **Source:** design/edge-cases.md E22 + p1411 finding M3 (policy clarity)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `ClaudeLaunchSpec` where:
- `appended_system_prompt = "meridian-skill-body"` (Meridian's value)
- `extra_args = ("--append-system-prompt", "user-override-prompt")` (user's value in extra args)

## When
`project_claude_spec_to_cli_args` runs.

## Then
- The canonical position contains Meridian's value: `--append-system-prompt meridian-skill-body`.
- The tail preserves the user's value: `--append-system-prompt user-override-prompt`.
- Both flags appear in the final command. Claude's own "last-wins" semantics mean the user's value takes effect.
- A warning log is emitted at projection time: "User passed known Meridian-managed flag in extra_args: --append-system-prompt (will last-win)".
- Subprocess and streaming paths produce identical output.

## Verification
- Unit test asserts both `--append-system-prompt` flags appear in the expected positions.
- Unit test asserts the warning log record is present with the expected message.
- Parity test asserts subprocess and streaming produce the same output for this input.

## Result (filled by tester)
_pending_
