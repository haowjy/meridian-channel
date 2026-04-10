# S042: Runner SIGTERM parity across subprocess and streaming

- **Source:** design/edge-cases.md E41 + decisions.md K8 (revision round 3)
- **Added by:** @design-orchestrator (revision round 3)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
A running spawn — tested once with subprocess transport, once with streaming transport (paired matrix across the three harnesses). The spawn is mid-turn, not at a natural completion boundary.

## When
The runner process receives `SIGTERM` (or `SIGINT`).

## Then
- The runner's signal handler translates the signal into exactly one `send_cancel()` invocation per active connection.
- Each connection emits its `cancelled` terminal event.
- The persisted terminal spawn status is `cancelled` on both transports, with the same semantics.
- No connection emits an error frame before the cancel frame.
- Crash-only reconciliation cleans up harness PID files and heartbeat artifacts on the next `meridian status` or `meridian spawn show`.
- The signal handler does not perform blocking I/O or allocate during handling — only sets cancellation intent and touches fds.

## Verification
- Smoke test: launch a streaming Codex spawn with a long-running prompt, send `SIGTERM` to the runner process, inspect the spawn store for terminal status and event ordering.
- Repeat for streaming Claude, streaming OpenCode, and a subprocess variant of each harness.
- Assert all six fixtures converge to identical terminal status and event shape.
- Regression fixture: fake cancellation that does NOT emit the event (temporarily disable the event emit) and verify the smoke test fails loudly.

## Result (filled by tester)
_pending_
