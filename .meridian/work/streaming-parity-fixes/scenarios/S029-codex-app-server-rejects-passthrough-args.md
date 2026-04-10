# S029: `codex app-server` rejects passthrough args surfaces cleanly

- **Source:** design/edge-cases.md E29 + p1411 finding M7
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
Codex streaming spawn with `extra_args=("--invalid-flag",)`. Real `codex app-server` is available (it does NOT accept `--invalid-flag`).

## When
The streaming runner launches Codex and forwards extra_args.

## Then
- Before launch, a debug log is emitted: "Forwarding passthrough args to codex app-server: ['--invalid-flag']".
- `codex app-server` fails at startup with its own error about the unknown flag.
- The failure is surfaced via the runner's existing error path — same structured error as any other failed launch.
- The spawn report includes both the debug log (pre-launch forwarding notice) and the Codex-side error (post-launch failure).
- No silent swallowing. No misleading "Codex crashed internally" message when the real cause is an argument the runner passed through.

## Verification
- Smoke test: run a Codex streaming spawn with `extra_args=("--invalid-flag",)`, capture debug.jsonl and the report.
- Assert the debug log entry is present.
- Assert the Codex error (unknown flag) is visible in the report.
- Assert the exit code is non-zero and matches the launcher's error-exit contract.
- Delta test: remove the pre-launch debug log and confirm diagnosing the failure becomes harder (this is qualitative — the test exists to lock in the debug log presence).

## Result (filled by tester)
_pending_
