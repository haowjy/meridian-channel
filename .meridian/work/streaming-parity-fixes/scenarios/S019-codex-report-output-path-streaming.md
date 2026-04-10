# S019: Codex `report_output_path` on streaming path

- **Source:** design/edge-cases.md E19 + p1411 finding M5
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Codex spawn with `report_output_path="/tmp/report.md"`. Two cases: subprocess path and streaming path.

## When
The adapter produces a `CodexLaunchSpec` and each runner projects it.

## Then
- **Subprocess:** the projected command contains `-o /tmp/report.md` (Codex CLI flag).
- **Streaming:** the field is NOT written to the `codex app-server` launch command (app-server has no equivalent flag).
- **Streaming:** a debug log is emitted: "Codex streaming ignores report_output_path; reports extracted from artifacts".
- Neither path crashes when the field is present. Neither path silently drops the field without logging on streaming.

## Verification
- Unit test: subprocess projection with `report_output_path` set; assert `-o /tmp/report.md` present.
- Unit test: streaming projection with the same spec; assert no `-o` flag, and capture the debug log (verify log record with the expected message).
- Unit test: streaming projection without `report_output_path` (None); no debug log about ignoring.

## Result (filled by tester)
_pending_
