# Normalized Schema

> What this is: the canonical backend-side schema between harness adapters and
> shell orchestration.
>
> What this is not: the frontend wire format. That derives from this document.

Back up to [overview.md](./overview.md).

## 1. Contract Rules

- This schema is canonical.
- Translators wrap and rename it; they do not synthesize missing identity or
  lifecycle edges.
- The normalized `UserMessage` command carries the **content-block array**
  directly. Adapters do any harness-specific attachment packaging themselves.

## 2. Wire Contract

**VERSION:** `1.0`

**Canonical source-of-truth when implemented:**

- `src/meridian/shell/schemas/events.py`
- `src/meridian/shell/schemas/commands.py`

**Compatibility rule:** additive-only for V0. Existing fields and event names do
not change in-place.

### Event Envelope

```json
{
  "version": "1.0",
  "seq": 42,
  "session_id": "sess_001",
  "turn_id": "turn_017",
  "event_type": "tool_call.started",
  "body": {}
}
```

Required envelope fields:

| Field | Meaning |
|---|---|
| `version` | normalized schema version |
| `seq` | per-session monotonic sequence |
| `session_id` | active shell session |
| `turn_id` | current turn when applicable; omitted for pure session events |
| `event_type` | normalized event discriminator |
| `body` | event-specific payload |

### Command Envelope

```json
{
  "version": "1.0",
  "command": "send_user_message",
  "body": {}
}
```

## 3. Normalized Commands

### `send_user_message`

```json
{
  "version": "1.0",
  "command": "send_user_message",
  "body": {
    "message_id": "msg_001",
    "content": [
      { "kind": "text_markdown", "text": "Review this mesh." },
      { "kind": "image_ref", "uri": "work://images/mesh-preview.png" }
    ],
    "turn_hints": {
      "previous_turn_id": "turn_016"
    }
  }
}
```

`content` is the canonical attachment carrier. Adapters map that structure into
Claude/Codex/OpenCode-native message forms.

### Other Commands

- `inject_user_message`
- `interrupt_turn`
- `submit_tool_result`
- `close_session`

## 4. Normalized Events

V0 needs this event family:

| Event | Body fields |
|---|---|
| `session.started` | `capabilities`, `adapter_id` |
| `turn.started` | `message_id` |
| `assistant.message.delta` | `message_id`, `delta` |
| `assistant.message.completed` | `message_id` |
| `assistant.reasoning.delta` | `message_id`, `delta` |
| `tool_call.started` | `tool_call_id`, `tool_name` |
| `tool_call.arguments.delta` | `tool_call_id`, `delta` |
| `tool_call.completed` | `tool_call_id` |
| `tool_call.output.delta` | `tool_call_id`, `stream`, `delta` |
| `content_block.published` | `tool_call_id`, `block` |
| `turn.finished` | `finish_reason` |
| `turn.error` | `code`, `message` |
| `session.resync_required` | `reason`, `state_digest` |

`content_block.published` is how local tool output, packaged MCP output, and
extension-backed displays share one publication path.

## 5. Content Block Shape

The normalized content block is the backend-side payload unit:

```json
{
  "block_id": "blk_002",
  "kind": "mesh.3d",
  "title": "Femur Mesh",
  "data": {
    "mesh_uri": "work://outputs/femur.glb"
  }
}
```

Known V0 built-in kinds are documented in
[../frontend/content-blocks.md](../frontend/content-blocks.md). Extension kinds
use namespaced values such as `mesh.3d` or `dicom.stack`.

## 6. Example Event

```json
{
  "version": "1.0",
  "seq": 51,
  "session_id": "sess_001",
  "turn_id": "turn_017",
  "event_type": "content_block.published",
  "body": {
    "tool_call_id": "tool_009",
    "block": {
      "block_id": "blk_002",
      "kind": "table",
      "title": "Summary Statistics",
      "data": {
        "columns": ["metric", "value"],
        "rows": [["femur_w_l_ratio", 1.23]]
      }
    }
  }
}
```

## 7. Read Next

- [flow.md](./flow.md)
- [../frontend/protocol.md](../frontend/protocol.md)
