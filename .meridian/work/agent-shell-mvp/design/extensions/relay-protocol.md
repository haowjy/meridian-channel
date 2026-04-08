# Relay Protocol

> What this is: the published frontend↔backend↔paired-MCP contract for
> interaction-layer extensions.
>
> What this is not: a direct browser↔MCP API.

Back up to [overview.md](./overview.md).

## 1. Wire Contract

**VERSION:** `1.0`

**Canonical source-of-truth when implemented:**

- `src/meridian/shell/schemas/relay.py`
- `frontend/src/lib/relay-types.ts`

**Compatibility rule:** additive-only for V0.

### Envelope

```json
{
  "version": "1.0",
  "relayId": "relay_001",
  "extensionId": "biomed.mesh-viewer",
  "direction": "ui_to_mcp",
  "eventType": "roi_selected",
  "payload": {}
}
```

Required fields:

| Field | Meaning |
|---|---|
| `version` | relay protocol version |
| `relayId` | one mounted extension session |
| `extensionId` | installed extension identifier |
| `direction` | `backend_to_ui`, `ui_to_mcp`, `mcp_to_ui`, or `mcp_to_agent` |
| `eventType` | extension-defined event name |
| `payload` | event body |

## 2. Lifecycle Frames

V0 relay ops:

- `relay_open`
- `relay_frame`
- `relay_close`
- `relay_error`

The backend owns channel establishment and teardown. Frontend and MCP only see
frames routed through the backend.

## 3. Example

```json
{
  "version": "1.0",
  "relayId": "relay_001",
  "extensionId": "biomed.mesh-viewer",
  "direction": "ui_to_mcp",
  "eventType": "landmarks_confirmed",
  "payload": {
    "labels": ["lateral", "medial"],
    "points": [[1.2, 3.4, 5.6], [7.8, 9.0, 1.2]]
  }
}
```

The paired MCP may respond with:

- a relay-only update for the UI,
- a new `content_block` for the transcript, or
- an agent-visible result that feeds the next turn.

## 4. Why Relay, Not Direct MCP

- preserves local-to-hosted continuity,
- keeps audit and policy hooks in one place,
- avoids exposing MCP transport internals to browser code, and
- lets the shell remain the source of truth for mounted extension state.

## 5. Read Next

- [interaction-layer.md](./interaction-layer.md)
- [../events/flow.md](../events/flow.md)
