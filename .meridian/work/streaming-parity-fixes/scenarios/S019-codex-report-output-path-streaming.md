# S019: Codex `report_output_path` on streaming path

- **Source:** design/edge-cases.md E19 + p1411 M5
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Codex spec sets `report_output_path`.

## When
Subprocess and streaming Codex projections run.

## Then
- Subprocess emits `-o <path>`.
- Streaming emits no wire flag for the field.
- Streaming logs:
  `Codex streaming ignores report_output_path; reports extracted from artifacts`.

## Verification
- Unit assertions for subprocess `-o` output.
- Caplog assertion for streaming debug message.
- No debug message when field is `None`.

## Result (filled by tester)
_pending_
