# S007: Streaming Codex with `sandbox=read-only`

- **Source:** design/edge-cases.md E7 + p1411 finding H1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
User spawns a Codex streaming task with `PermissionConfig(sandbox="read-only", approval="auto")`. The real `codex app-server` binary is installed and on PATH.

## When
The streaming runner launches Codex via `project_codex_spec_to_appserver_command`.

## Then
- The launch command contains `-c sandbox_mode="read-only"` (verified against real `codex app-server --help` output at implementation time).
- Debug trace confirms the flag reaches the Codex process.
- A write operation attempted inside the sandboxed Codex session is rejected by Codex.
- No silent downgrade: removing the flag must cause the test to fail.

## Verification
- Run `uv run meridian spawn -a coder -m codex -p "try to write /tmp/hack" --sandbox read-only`.
- Capture the `debug.jsonl` for the spawn and confirm the sandbox override line.
- Inspect the spawn report and confirm the write attempt was rejected.
- Delta test: flip the projection temporarily to omit the override, rerun, and confirm the write succeeds (this proves the flag was the reason — not a default).
- Compare against the subprocess path for the same inputs; the sandbox-related behavior must match.

## Result (filled by tester)
_pending_
