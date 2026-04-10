# S015: Claude spec round-trip with every field populated

- **Source:** design/edge-cases.md E15 + p1411 findings M3 + H2
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `ClaudeLaunchSpec` with every field populated:
- `model="claude-opus-4-6"`
- `effort="hard"`
- `agent_name="reviewer"`
- `appended_system_prompt="meridian-skill-body"`
- `agents_payload='{"reviewer": {...}}'`
- `continue_session_id="sess-123"`
- `continue_fork=True`
- `permission_resolver=ExplicitToolsResolver(allowed=("Read","Edit"), denied=("Bash",))`
- `extra_args=("--foo","bar")`
- `interactive=False`

## When
The spec is projected to CLI args via `project_claude_spec_to_cli_args` for both `SUBPROCESS_BASE` and `STREAMING_BASE`.

## Then
- Both paths emit every spec field on the wire (nothing silently dropped).
- The canonical order after the base command is:
  `--model → --effort → --agent → --append-system-prompt → --agents → --resume → --fork-session → perm_flags merged with extra_args (deduped on --allowedTools) → remaining extra_args`
- Arg tails are byte-equal between subprocess and streaming.
- No duplicate `--allowedTools`. No out-of-order flags.

## Verification
- Unit test asserts each flag is present exactly once with the expected value.
- Positional assertions: check the index of each flag relative to the base command length.
- Parity assertion: `subprocess_tail == streaming_tail`.
- Field-coverage assertion: iterate over `ClaudeLaunchSpec.model_fields` and confirm every field is reflected somewhere in the output (either as a flag or as a delegated field in `_SPEC_DELEGATED_FIELDS`).

## Result (filled by tester)
_pending_
