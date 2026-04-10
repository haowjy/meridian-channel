# S033: Debug log for passthrough args on streaming

- **Source:** design/edge-cases.md E33 + p1411 finding M7
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier (+ @unit-tester)
- **Status:** pending

## Given
A streaming spawn (Codex or OpenCode) with a non-empty `extra_args` tuple on the spec.

## When
The projection function (`project_codex_spec_to_appserver_command` / `project_opencode_spec_to_http_payload`) constructs the launch command or payload.

## Then
- A debug-level log record is emitted at the projection site listing the forwarded args verbatim: `"Forwarding passthrough args to <harness> streaming: ['--foo','bar',...]"`.
- The log appears once per projection call.
- The log level is DEBUG (not INFO, not WARNING) — it is diagnostic, not operational.
- Empty `extra_args` produces no log record.

## Verification
- Unit test: invoke the projection with non-empty extra_args under `caplog.at_level(logging.DEBUG)`; assert the expected log record is present.
- Unit test: invoke with empty extra_args; assert no passthrough-forwarding log record.
- Log capture in an integration test via `caplog` confirms the message format and that it is at DEBUG level.
- Document the convention in the projection docstring so future harness additions follow the same logging convention.

## Result (filled by tester)
_pending_
