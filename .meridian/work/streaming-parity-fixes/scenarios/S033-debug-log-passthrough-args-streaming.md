# S033: Debug log for passthrough args on streaming

- **Source:** design/edge-cases.md E33 + p1411 M7
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier (+ @unit-tester)
- **Status:** pending

## Given
Streaming spec has non-empty `extra_args`.

## When
Projection functions run:

- `project_codex_spec_to_appserver_command`
- `project_opencode_spec_to_serve_command`

## Then
- DEBUG log records forwarded passthrough args once per projection call.
- Empty `extra_args` emits no passthrough debug log.

## Verification
- Caplog assertions for both functions.
- Negative case with empty args.

## Result (filled by tester)
_pending_
