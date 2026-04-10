# S028: Harness binary missing from PATH

- **Source:** design/edge-cases.md E28 (parity contract for error handling)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
`claude` / `codex` / `opencode` binaries are removed from `PATH` (or PATH is set to a directory that does not contain them).

## When
A spawn is launched via each runner (subprocess and streaming) for each harness.

## Then
- Both runners emit the same structured error for each harness: `HarnessBinaryNotFound` (or the shared error class).
- The error message names the binary and the PATH that was searched.
- The exit code matches between runners: both surface the infra-level exit code (e.g., `127`).
- No silent fallback to `/bin/sh: claude: command not found` — the error is caught at the binary-locate step and surfaced cleanly.
- Spawn report contains the structured error, not a raw subprocess traceback.

## Verification
- Smoke test: with an empty PATH (or PATH stripped of the harness), run `uv run meridian spawn` for each of the 6 combinations (3 harnesses × 2 runners), capture the exit code and the report.
- Assert the 6 reports contain matching error class / message structure.
- Assert the exit codes match across runner pairs for the same harness.
- Parity: subprocess runner and streaming runner error outputs differ only in the runner-identification metadata, not in the error semantics.

## Result (filled by tester)
_pending_
