# Direct Harness Adapter

Source: `src/meridian/lib/harness/direct.py`

## What It Is

An in-process `InProcessHarness` implementation that calls the Anthropic Messages API directly (no subprocess). Used for lightweight automation tasks that need to call Meridian operations programmatically — the tool definitions are generated from the ops manifest.

## Capabilities

Only `supports_programmatic_tools=True`. No stream events, no session resume, no session fork, no native skills.

## How It Works

`execute(prompt, model, **kwargs)` runs an async tool-calling loop:
1. Builds tool definitions from `get_operations_for_surface("mcp")` — generates Anthropic tool schemas from every operation registered on the MCP surface
2. Includes a `code_execution` tool (`{"type": "code_execution_20260120", "name": "code_execution"}`)
3. All non-code-execution tools have `"allowed_callers": ["code_execution_20260120"]` — they can only be invoked from within code execution, not directly
4. Sends initial message to Anthropic Messages API
5. Loops: if response contains tool calls, executes them against the operation handlers, feeds results back, continues until no more tool calls

## Tool Definition Generation

`build_tool_definitions()` iterates `get_operations_for_surface("mcp")` and calls `schema_from_type(operation.input_type)` for each. This means the Direct adapter's tool surface is exactly the MCP surface — they stay in sync automatically via the shared manifest.

## Why It Exists

Enables Meridian to call itself programmatically without spawning a full Claude/Codex/OpenCode subprocess. Useful for internal coordination tasks where you want tool-calling behavior against Meridian's own operation set but don't need a full agent session.

## Limitations

- No session continuity — each `execute()` call is stateless
- No streaming — full response is returned at once
- Requires `ANTHROPIC_API_KEY` in environment
- No conversation history management — single-shot calls only
- Not intended for user-facing spawns; used internally
