# S011: Streaming Claude dedupes parent `--allowedTools`

- **Source:** design/edge-cases.md E11 + p1411 finding H2
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester (+ @unit-tester for projection unit)
- **Status:** pending

## Given
- `CLAUDECODE=1` in the parent environment.
- Parent `.claude/settings.json` grants `allowedTools=["Read", "Bash"]`.
- Spawn uses `ExplicitToolsResolver(allowed_tools=("Read", "Edit"))`.
- Streaming runner invokes `read_parent_claude_permissions` preflight.

## When
The streaming runner builds the Claude command via `project_claude_spec_to_cli_args`.

## Then
- The final launched command contains **exactly one** `--allowedTools` flag.
- Its value is the deduped order-preserving union: `Read,Edit,Bash` (or equivalent canonical ordering defined in the projection).
- No duplicate flags. No dropped tools. No silent overwrite by the later flag.
- Byte-identical to the subprocess output for the same inputs (paired with S012).

## Verification
- Unit test: construct the scenario inputs, call `project_claude_spec_to_cli_args`, assert `list.count("--allowedTools") == 1` and the value matches the expected union.
- Smoke test: launch a real streaming Claude spawn with `CLAUDECODE=1`, parent settings file populated, and inspect the process args (via `ps`, `/proc/<pid>/cmdline`, or command logging) for exactly one `--allowedTools` flag.
- Delta test: temporarily disable the projection's dedupe and confirm this test fails.

## Result (filled by tester)
_pending_
