# S047: `mcp_tools` is projected into every harness's wire format

- **Source:** design/edge-cases.md E47 + decisions.md D4 (revision round 3)
- **Added by:** @design-orchestrator (revision round 3)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `ResolvedLaunchSpec` (per harness) with `mcp_tools = ("codex-mcp=/usr/local/bin/codex-mcp", "other=/opt/other")` (two entries in the Codex name=command form). For Claude, the same conceptual input uses path-style entries. For OpenCode, the session-payload server list form.

## When
Each of the six projection functions runs on its respective spec subclass.

## Then
- Claude subprocess: command contains `--mcp-config codex-mcp=/usr/local/bin/codex-mcp --mcp-config other=/opt/other` (one `--mcp-config` per entry, in order).
- Claude streaming: same canonical ordering, identical to subprocess.
- Codex subprocess: command contains `-c mcp.servers.codex-mcp.command="/usr/local/bin/codex-mcp" -c mcp.servers.other.command="/opt/other"`.
- Codex streaming (`project_codex_spec_to_appserver_command`): same `-c mcp.servers.*.command=...` emission at the canonical position, before `spec.extra_args`.
- OpenCode subprocess: CLI args include the MCP projection (if `opencode run` supports CLI MCP; otherwise env-only path).
- OpenCode streaming (`project_opencode_spec_to_session_payload`): HTTP payload has `mcp: {"servers": ["codex-mcp=/usr/local/bin/codex-mcp", "other=/opt/other"]}`.
- Empty `mcp_tools = ()` produces no wire-level MCP state on any harness (no empty `--mcp-config`, no empty `-c mcp.servers`, no empty `mcp` key in the payload).

## Verification
- Six unit tests (one per projection) asserting the exact wire output for the two-entry fixture.
- Six unit tests asserting empty `mcp_tools` produces no MCP-related output.
- Cross-check: assert `mcp_tools` appears in every projection's `_PROJECTED_FIELDS` set and every adapter's `handled_fields`.
- Drift guard: `_check_projection_drift` fails if any projection omits `mcp_tools`.

## Result (filled by tester)
_pending_
