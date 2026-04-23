# MCP Tools

`meridian serve` exposes Meridian operations as FastMCP tools over stdio.

The MCP server provides two tools: `extension_list_commands` and `extension_invoke`. These give agents full access to all registered extension commands across the extension system.

## Start Server

```bash
meridian serve
```

Minimal MCP config:

```json
{
  "mcpServers": {
    "meridian": {
      "command": "meridian",
      "args": ["serve"]
    }
  }
}
```

## Tools

### `extension_list_commands`

No arguments. Returns all extension commands registered on the MCP surface with their `fqid`, `summary`, `surfaces`, and `requires_app_server`.

```json
{}
```

Response:

```json
{
  "schema_version": 1,
  "manifest_hash": "a3f9c2b1d8e74f06",
  "commands": [
    {
      "fqid": "meridian.sessions.archiveSpawn",
      "extension_id": "meridian.sessions",
      "command_id": "archiveSpawn",
      "summary": "Archive a completed spawn to hide it from default listings",
      "surfaces": ["cli", "http", "mcp"],
      "requires_app_server": true
    }
  ]
}
```

The `manifest_hash` is a short hash of all command schemas and metadata. Cache the manifest and re-check the hash to detect when the registry has changed.

### `extension_invoke`

Invoke any registered extension command by its fully qualified ID.

```json
{
  "fqid": "meridian.sessions.getSpawnStats",
  "args": { "spawn_id": "p42" },
  "request_id": "req-abc123",
  "work_id": "auth-refactor",
  "spawn_id": "p42"
}
```

Only `fqid` is required. `args` defaults to `{}`. `request_id`, `work_id`, and `spawn_id` are optional context passed to the handler for tracing.

**Success:** `{"status": "ok", "result": {...}}`

**Error:** `{"status": "error", "code": "...", "message": "..."}`

Common error codes: `not_found`, `surface_not_allowed`, `args_invalid`, `app_server_required`, `app_server_stale`, `app_server_unreachable`, `capability_missing`, `handler_error`.

**Routing.** Commands with `requires_app_server: false` run in-process — no HTTP round-trip. Commands with `requires_app_server: true` locate the running app server and invoke over HTTP automatically.

## Spawn Statuses

Extension commands that return spawn records carry a `status` field with one of these values:

| Status | Meaning |
| ------ | ------- |
| `queued` | Registered; harness not yet started |
| `running` | Harness process is active |
| `finalizing` | All post-exit work is done; runner is committing the terminal state — not yet terminal |
| `succeeded` | Completed successfully |
| `failed` | Completed with an error |
| `cancelled` | Cancelled before or during execution |

`queued`, `running`, and `finalizing` are active (in-flight). `succeeded`, `failed`, and `cancelled` are terminal. `finalizing` is typically brief but is visible in responses between harness exit and final persistence. Treat it the same as `running` when deciding whether to poll again.

See [extensions.md](extensions.md) for the full extension command reference including the HTTP API and CLI details.
