// ═══════════════════════════════════════════════════════════════════
// Data model — stored in state, updated by AG-UI SSE events
//
// Streaming-first: fields populate progressively as events arrive.
//
// TOOL_CALL_START  → ToolItem created, toolName set, status = "streaming-args"
// TOOL_CALL_ARGS   → argsText accumulates, parsedArgs updated via partial-json
// TOOL_CALL_END    → status = "executing"
// TOOL_CALL_RESULT → resultText set, status = "done" | "error"
// ═══════════════════════════════════════════════════════════════════

export type ToolStatus = "streaming-args" | "executing" | "done" | "error"

export type ThinkingItem = {
  kind: "thinking"
  id: string
  text: string
}

export type ContentItem = {
  kind: "content"
  id: string
  text: string
}

/**
 * A tool call in the activity stream.
 *
 * Every tool follows the same shape — Read, Bash, Agent, unknown MCP tools.
 * The rendering layer decides how to display based on toolName + parsedArgs.
 *
 * Header renders progressively:
 *   Tool()  →  Read("pat")  →  Read("path/to/file.tsx")
 *
 * Detail card shows input (argsText) streaming in, then output (resultText).
 */
export type ToolItem = {
  kind: "tool"
  id: string
  /** Tool name from TOOL_CALL_START. Undefined before START arrives → renders as "Tool". */
  toolName?: string
  status: ToolStatus
  /** Raw accumulated JSON from TOOL_CALL_ARGS deltas. */
  argsText: string
  /** Best-effort partial parse of argsText (via partial-json). Updates on each delta. */
  parsedArgs?: Record<string, unknown>
  /** Result string from TOOL_CALL_RESULT. */
  resultText?: string
  /** Whether the tool result is an error. */
  isError?: boolean
  /** Nested activity for agent/sub-agent tools (built up as nested events arrive). */
  nestedActivity?: ActivityBlockData
}

export type ActivityItem = ThinkingItem | ContentItem | ToolItem

export type ActivityBlockData = {
  id: string
  items: ActivityItem[]
  pendingText?: string
  isStreaming?: boolean
  /** Set by RUN_ERROR — the error message from the backend. */
  error?: string
  /** Set by RUN_ERROR — whether the error was a user-initiated cancellation. */
  isCancelled?: boolean
}

// ═══════════════════════════════════════════════════════════════════
// Rendering types — used by detail components for rich display.
// Not stored in state; computed from ToolItem data during render.
// ═══════════════════════════════════════════════════════════════════

export type DiffLine = {
  type: "context" | "add" | "remove"
  text: string
}