# Harness Abstraction

> What this is: the session-lived adapter boundary the shell depends on.
>
> What this is not: the canonical event schema or the package-loading flow.

Back up to [overview.md](./overview.md).

## 1. Responsibilities

The shell depends on one harness-facing surface:

- start and stop a session,
- send user messages,
- inject or interrupt mid-turn input according to harness semantics,
- surface normalized events, and
- accept locally produced tool results.

The shell does **not** depend on any harness-native JSON shape, process argv,
or HTTP endpoint outside the adapter module that implements that harness.

## 2. Protocol Split

The adapter boundary is intentionally narrow:

| Protocol | Responsibility |
|---|---|
| `HarnessLifecycle` | launch, health, close, optional resume metadata |
| `HarnessSender` | send turn-start messages, mid-turn inject, interrupt, submit tool result |
| `HarnessReceiver` | emit normalized events from the active session |
| `HarnessAdapter` | the composite used by `SessionContext` and `TurnOrchestrator` |

Adding a harness is one new adapter file plus registration. Router,
translator, relay, and frontend code do not change.

## 3. Normalized Command Surface

The canonical event schema lives in [../events/normalized-schema.md](../events/normalized-schema.md).
The command side is fixed here because the sender boundary is what keeps tool
resumption and mid-turn control harness-neutral.
This command surface inherits VERSION `1.0` from the normalized event schema
and evolves under the same additive-only V0 rule.

| Command | Purpose |
|---|---|
| `start_session(SessionContext)` | launch the harness with resolved prompt, working directory, and MCP config |
| `send_user_message(UserMessage)` | begin the next turn |
| `inject_user_message(turn_id, UserMessage)` | deliver mid-turn steering input using the adapter's declared mode |
| `interrupt_turn(turn_id)` | stop the active turn when supported |
| `submit_tool_result(tool_call_id, result, status)` | resume the harness after local or packaged tool work completes |
| `close()` | terminate the adapter-owned session |

`submit_tool_result` is mandatory. The shell never writes Claude-specific
`tool_result` frames or Codex-specific RPC directly.

## 4. Capability Semantics

The adapter publishes **effective** behavior, not theoretical protocol
headroom:

- `mid_turn_injection`: `queue`, `interrupt_restart`, `http_post`, or `none`
- `supports_interrupt`
- `supports_session_resume`
- `supports_tool_approval`
- `supports_structured_reasoning`

If Claude queue-mode fails the required verification spike, Claude V0 reports
`mid_turn_injection="none"`. The seam stays the same; only the declared
capability changes.

## 5. Dependencies

- The harness layer depends on `SessionContext` from
  [../packaging/agent-loading.md](../packaging/agent-loading.md).
- It emits normalized events defined in
  [../events/normalized-schema.md](../events/normalized-schema.md).
- It does not know how packages are installed, how the frontend renders blocks,
  or how packaged MCP servers manage their own internal runtimes.

## 6. Explicit Non-Goals

- No shell-owned biomedical kernel.
- No shell-owned PyVista viewer or DICOM logic.
- No second adapter family for interactive tools.
- No resolution of Q7 in this pass.
