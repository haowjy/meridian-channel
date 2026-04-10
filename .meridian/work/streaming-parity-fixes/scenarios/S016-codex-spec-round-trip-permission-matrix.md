# S016: Codex spec round-trip with every permission combo

- **Source:** design/edge-cases.md E16 + p1411 finding H1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester (parametrized) + @smoke-tester (sample cells)
- **Status:** pending

## Given
A 4×4 matrix of `CodexLaunchSpec` configurations:
- `sandbox ∈ {default, read-only, workspace-write, danger-full-access}`
- `approval ∈ {default, auto, yolo, confirm}`

All other fields held constant.

## When
Each cell is projected via both the subprocess runner (`project_codex_spec_to_cli_args`) and the streaming runner (`project_codex_spec_to_appserver_command`).

## Then
- Subprocess emits the appropriate `--sandbox` / `--full-auto` / `--ask-for-approval` combo via `permission_resolver.resolve_flags`.
- Streaming emits the appropriate `-c sandbox_mode=<v>` and `-c approval_policy=<v>` overrides (or the verified-at-impl equivalent — **adapter must probe `codex app-server --help` before committing to flag names**).
- Every cell produces a distinct wire format — no two cells collapse to the same command.
- `sandbox=default` AND `approval=default` both correctly omit their respective overrides (letting Codex apply its own default).
- No cell silently collapses to accept-all or danger-full-access.

## Verification
- Parametrized pytest over all 16 cells; assert each produces expected output for both paths.
- Round-trip test: for each cell, parse the generated command back and confirm the semantic match.
- Smoke test: pick 4 representative cells (one per sandbox level) and run them against real `codex app-server`. Verify observed behavior matches expectation (read-only rejects writes, workspace-write allows cwd writes, etc.).
- Confirm no cell reduces to `if approval != 'confirm': accept_all` (the v1 collapse bug).

## Result (filled by tester)
_pending_
