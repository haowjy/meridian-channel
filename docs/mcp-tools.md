# MCP Tools

`meridian serve` exposes all operations as MCP tools. An MCP-aware agent (Claude, etc.) calls these tools programmatically instead of parsing CLI stdout.

## Starting the Server

```bash
meridian serve
```

The server communicates over stdio using the MCP protocol (JSON-RPC). Configure it in your MCP client's settings:

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

## Key Difference: Non-Blocking `run_create`

In MCP mode, `run_create` returns immediately with `status: "running"`. The agent then polls with `run_show` or blocks with `run_wait`:

```
Agent -> run_create(prompt="Fix the bug", model="codex")
      <- {status: "running", run_id: "r1"}
Agent -> run_wait(run_id="r1", timeout_secs=300)
      <- {status: "succeeded", run_id: "r1", report: "..."}
```

This prevents the MCP connection from hanging during long runs.

## Tool Reference

### Run Management

#### `run_create`

Create and start a new agent run.

```json
{
  "prompt": "Refactor the auth module",
  "model": "gpt-5.3-codex",
  "skills": ["scratchpad"],
  "files": ["plan.md"],
  "template_vars": {"TARGET": "auth"},
  "agent": "coder",
  "timeout_secs": 600,
  "permission": "workspace-write",
  "budget_per_run_usd": 5.0,
  "secrets": {"API_KEY": "sk-..."}
}
```

Returns: `RunActionOutput` with `run_id`, `status`, `exit_code`, `report`, `composed_prompt` (dry-run), `cli_command` (dry-run).

#### `run_list`

List runs with optional filters.

```json
{
  "workspace_id": "w1",
  "status": "failed",
  "model": "codex",
  "limit": 10,
  "standalone_only": false
}
```

Returns: `RunListOutput` with list of run summaries.

#### `run_show`

Get run details.

```json
{
  "run_id": "r1",
  "include_report": true,
  "include_files": true
}
```

Returns: `RunDetailOutput` with full run metadata, optional report text and files-touched list.

#### `run_continue`

Continue a previous run with a follow-up prompt.

```json
{
  "run_id": "r1",
  "prompt": "Also update the tests",
  "model": "claude-opus-4-6"
}
```

#### `run_retry`

Retry a failed run.

```json
{
  "run_id": "r3",
  "prompt": "Try with more context",
  "model": "opus"
}
```

#### `run_wait`

Block until a run reaches terminal status.

```json
{
  "run_id": "r1",
  "timeout_secs": 300,
  "include_report": true
}
```

### Workspace Management

#### `workspace_start`

Create a workspace and launch supervisor.

```json
{
  "name": "auth-refactor",
  "model": "claude-opus-4-6",
  "autocompact": 80
}
```

#### `workspace_resume`

Resume a paused workspace.

```json
{
  "workspace_id": "w1",
  "fresh": false,
  "model": "claude-opus-4-6"
}
```

#### `workspace_list`

```json
{ "limit": 10 }
```

#### `workspace_show`

```json
{ "workspace_id": "w1" }
```

#### `workspace_close`

```json
{ "workspace_id": "w1" }
```

### Context Pinning

#### `context_pin`

```json
{
  "file_path": "docs/architecture.md",
  "workspace_id": "w1"
}
```

#### `context_unpin`

```json
{
  "file_path": "docs/architecture.md",
  "workspace_id": "w1"
}
```

#### `context_list`

```json
{ "workspace_id": "w1" }
```

### Skills & Models

#### `skills_list`

```json
{}
```

#### `skills_search`

```json
{ "query": "review" }
```

#### `skills_load`

```json
{ "name": "review" }
```

Returns full SKILL.md content.

#### `skills_reindex`

```json
{}
```

#### `models_list`

```json
{}
```

#### `models_show`

```json
{ "name": "opus" }
```

### Diagnostics

#### `diag_doctor`

```json
{}
```

Returns health checks: schema version, counts, directory presence.

#### `diag_repair`

```json
{}
```

Returns list of repairs performed.

## DirectAdapter (API Tools)

The `DirectAdapter` generates Anthropic API tool definitions from the same Operation Registry. These tools include `allowed_callers: ["code_execution_20260120"]` for programmatic tool calling via the Anthropic Messages API `code_execution` feature.

This enables agents running in `direct` mode (no CLI harness) to call meridian operations as native API tools.
