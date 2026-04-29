# Extensions

Extensions expose Meridian operations across three surfaces — CLI, HTTP, and MCP — from a single registration. A command registered once appears in `meridian ext run`, the HTTP API, and the MCP server without any per-surface wiring.

## meridian ext CLI

Discovery works with no app server running. Invocation (`ext run`) runs in-process for commands with `requires_app_server: false`. Commands with `requires_app_server: true` currently return `No app server running` while the old app server is archived for rebuild.

### List extensions

```
meridian ext list
```

Groups commands by extension namespace:

```
meridian.sessions
  archiveSpawn
  getSpawnStats
meridian.workbench
  ping
```

### Inspect an extension

```
meridian ext show meridian.sessions
```

```
Extension: meridian.sessions

  archiveSpawn
    Archive a completed spawn to hide it from default listings
    surfaces: cli, http, mcp
    requires_app_server: True

  getSpawnStats
    Get token usage and cost statistics for a spawn
    surfaces: cli, http, mcp
    requires_app_server: True
```

### List all commands

```
meridian ext commands
meridian ext commands --json    # stable JSON array for agent use
```

JSON output includes `schema_version`, `manifest_hash`, and a `commands` array. The `manifest_hash` changes when any command's schema, summary, or surfaces change — useful for cache invalidation.

### Run a command

```
meridian ext run FQID [--args JSON] [--work-id ID] [--spawn-id ID] [--request-id ID]
```

`FQID` is `extension_id.command_id`:

```bash
meridian ext run meridian.sessions.getSpawnStats --args '{"spawn_id": "p42"}'
```

Output is the command's JSON payload by default. Pass `--json` or `--format json` to wrap it in `{"result": ...}`. Errors always print to stderr in text mode; with `--json`, errors emit `{"status": "error", "code": ..., "message": ...}` to stdout.

**Exit codes**

| Code | Meaning |
| ---- | ------- |
| 0 | Success |
| 1 | Command not found or command returned error |
| 2 | App server unavailable |
| 7 | Invalid JSON `--args` (not valid JSON or not a JSON object) |

Code 2 is an app-server availability problem; code 7 is a caller error. Check exit codes in scripts to distinguish these cases.

---

## HTTP Extension API

The app server exposes extension commands over HTTP. All routes are under `/api/extensions/`.

### Discovery (no auth required)

**`GET /api/extensions`** — all extensions and their commands with full schemas.

```json
{
  "schema_version": 1,
  "manifest_hash": "a3f9c2b1d8e74f06",
  "extensions": [
    {
      "extension_id": "meridian.sessions",
      "commands": [
        {
          "command_id": "archiveSpawn",
          "summary": "Archive a completed spawn to hide it from default listings",
          "args_schema": { ... },
          "output_schema": { ... },
          "surfaces": ["cli", "http", "mcp"],
          "requires_app_server": true
        }
      ]
    }
  ]
}
```

**`GET /api/extensions/manifest-hash`** — fast hash check without full schema payload.

```json
{ "schema_version": 1, "manifest_hash": "a3f9c2b1d8e74f06" }
```

**`GET /api/extensions/{extension_id}`** — single extension detail.

**`GET /api/extensions/{extension_id}/commands`** — commands for one extension.

### Invocation (Bearer auth required)

```
POST /api/extensions/{extension_id}/commands/{command_id}/invoke
Authorization: Bearer <token>
Content-Type: application/json
```

Request body:

```json
{
  "args": { "spawn_id": "p42" },
  "request_id": "req-abc123",
  "work_id": "auth-refactor",
  "spawn_id": "p42"
}
```

All fields except `args` are optional context that handlers can use for tracing and audit.

Successful response:

```json
{
  "request_id": "req-abc123",
  "result": { "spawn_id": "p42", "input_tokens": 1200, "output_tokens": 340 }
}
```

**Authentication.** The Bearer token lives at `<runtime_root>/app/<pid>/token`. The `meridian ext run` CLI reads this automatically. External clients must read the file directly.

**Errors.** All error responses use [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `application/problem+json`:

```json
{
  "type": "urn:meridian:extension:error:not_found",
  "title": "Not Found",
  "status": 404,
  "detail": "Extension command not found: meridian.sessions.unknownCmd",
  "request_id": "req-abc123"
}
```

| HTTP status | Error code | Meaning |
| ----------- | ---------- | ------- |
| 401 | `unauthorized` | Missing or wrong Bearer token |
| 404 | `not_found` | Command not registered |
| 403 | `surface_not_allowed` | Command not available via HTTP |
| 403 | `capability_missing` | Command requires a capability the server hasn't granted |
| 422 | `args_invalid` | Args failed schema validation |
| 501 | `streaming_not_implemented` | `stream: true` not yet supported |
| 503 | `app_server_required` | Command requires app server but none available |
| 500 | `handler_error` | Unhandled exception in the handler |

---

## MCP Extension Tools

`meridian serve` exposes two tools for agents that need to discover and invoke extension commands.

### `extension_list_commands`

No arguments. Returns the same payload as `meridian ext commands --json`:

```json
{}
```

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

### `extension_invoke`

```json
{
  "fqid": "meridian.sessions.getSpawnStats",
  "args": { "spawn_id": "p42" },
  "request_id": "req-abc123",
  "work_id": "auth-refactor",
  "spawn_id": "p42"
}
```

`fqid` is required. All other fields are optional.

**Routing.** Commands with `requires_app_server: false` run in-process — no HTTP round-trip. Commands with `requires_app_server: true` locate the running app server and invoke over HTTP automatically.

**Success:**

```json
{ "status": "ok", "result": { ... } }
```

**Error:**

```json
{ "status": "error", "code": "not_found", "message": "Command not found: bad.fqid" }
```

Error codes mirror the HTTP surface. `app_server_required`, `app_server_stale`, `app_server_wrong_project`, and `app_server_unreachable` indicate server-state problems rather than command problems.
