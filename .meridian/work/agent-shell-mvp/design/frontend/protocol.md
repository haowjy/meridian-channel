# Frontend Protocol

> What this is: the published backend↔frontend wire contract for the generic
> chat UI.
>
> What this is not: the normalized adapter contract; that lives one layer below.

Back up to [overview.md](./overview.md).

## 1. Wire Contract

**VERSION:** `1.0`

**Canonical source-of-truth when implemented:**

- `src/meridian/shell/schemas/wire.py`
- `frontend/src/lib/wire-types.ts`

**Compatibility rule:** additive-only for V0.

### Envelope

```json
{
  "version": "1.0",
  "lane": "turn",
  "op": "content_block",
  "sessionId": "sess_001",
  "turnId": "turn_017",
  "payload": {}
}
```

`lane` values in V0:

- `session`
- `turn`
- `relay`
- `error`

## 2. Session Frames

### `session_hello`

The server must send this first:

```json
{
  "version": "1.0",
  "lane": "session",
  "op": "session_hello",
  "sessionId": "sess_001",
  "payload": {
    "agentProfile": "yao-lab-analyst",
    "adapter": "claude-code",
    "capabilities": {
      "midTurnInjection": "queue",
      "supportsInterrupt": true,
      "supportsToolApproval": false
    }
  }
}
```

If Claude queue mode is not verified, `midTurnInjection` becomes `none`.

### `session_resync`

Signals that replay is no longer available and the client must reset local
stream state.

## 3. Turn Frames

V0 turn ops:

- `turn_started`
- `assistant_message_delta`
- `assistant_message_completed`
- `assistant_reasoning_delta`
- `tool_call_started`
- `tool_call_arguments_delta`
- `tool_call_completed`
- `tool_output_delta`
- `content_block`
- `turn_finished`
- `turn_error`

`content_block` carries the frontend-side block object:

```json
{
  "blockId": "blk_002",
  "kind": "table",
  "title": "Summary Statistics",
  "data": {
    "columns": ["metric", "value"],
    "rows": [["femur_w_l_ratio", 1.23]]
  }
}
```

## 4. Client Commands

### `send_user_message`

**M1 disposition:** the command shape is:

```json
{
  "version": "1.0",
  "lane": "turn",
  "op": "send_user_message",
  "sessionId": "sess_001",
  "payload": {
    "messageId": "msg_001",
    "content": [
      { "kind": "text_markdown", "text": "Please review these landmarks." }
    ],
    "turnHints": {
      "previousTurnId": "turn_016"
    }
  }
}
```

This is the only accepted V0 shape. No alternate attachment carrier exists.

### Other Commands

- `cancel_turn`
- `inject_user_message`
- `ack_resync`

Relay-specific commands are defined in
[../extensions/relay-protocol.md](../extensions/relay-protocol.md).

## 5. Source Relationship To Normalized Schema

The frontend protocol is a rename layer over
[../events/normalized-schema.md](../events/normalized-schema.md). It may:

- convert `snake_case` to `camelCase`,
- collapse normalized dotted event names into flat frontend ops,
- split session vs turn vs relay lanes, and
- wrap normalized content blocks in frontend envelopes.

It may not invent a second lifecycle model.

### Event Translation Table

| Normalized event | Frontend lane | Frontend op |
|---|---|---|
| `session.started` | `session` | `session_hello` |
| `session.resync_required` | `session` | `session_resync` |
| `turn.started` | `turn` | `turn_started` |
| `assistant.message.delta` | `turn` | `assistant_message_delta` |
| `assistant.message.completed` | `turn` | `assistant_message_completed` |
| `assistant.reasoning.delta` | `turn` | `assistant_reasoning_delta` |
| `tool_call.started` | `turn` | `tool_call_started` |
| `tool_call.arguments.delta` | `turn` | `tool_call_arguments_delta` |
| `tool_call.completed` | `turn` | `tool_call_completed` |
| `tool_call.output.delta` | `turn` | `tool_output_delta` |
| `content_block.published` | `turn` | `content_block` |
| `turn.finished` | `turn` | `turn_finished` |
| `turn.error` | `turn` | `turn_error` |

This table is exhaustive for V0. Any new normalized event must publish its
frontend counterpart in this table before the frontend protocol changes.

## 6. Read Next

- [chat-ui.md](./chat-ui.md)
- [content-blocks.md](./content-blocks.md)
- [../extensions/relay-protocol.md](../extensions/relay-protocol.md)
