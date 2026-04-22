/**
 * AG-UI protocol event types for the activity stream reducer.
 *
 * Event type names and field names match the official AG-UI protocol
 * (github.com/ag-ui-protocol/ag-ui). Self-contained — no external
 * dependency needed until we integrate the real SSE layer.
 *
 * Differences from raw AG-UI:
 * - THINKING_START carries a `thinkingId` (Meridian extension — AG-UI
 *   doesn't natively ID thinking blocks, so the backend adds one)
 * - TOOL_CALL_RESULT carries `isError` (Meridian extension)
 * - RESET is client-only (simulator restart)
 * - RUN_ERROR is Meridian-extended (adds isCancelled)
 */

export type StreamEvent =
  // Lifecycle
  | { type: "RUN_STARTED" }
  | { type: "RUN_FINISHED" }
  | { type: "RUN_ERROR"; message: string; isCancelled?: boolean }
  // Text messages
  | { type: "TEXT_MESSAGE_START"; messageId: string }
  | { type: "TEXT_MESSAGE_CONTENT"; messageId: string; delta: string }
  | { type: "TEXT_MESSAGE_END"; messageId: string }
  // Thinking (AG-UI official names)
  | { type: "THINKING_START"; thinkingId: string }
  | { type: "THINKING_TEXT_MESSAGE_START"; thinkingId: string }
  | { type: "THINKING_TEXT_MESSAGE_CONTENT"; thinkingId: string; delta: string }
  | { type: "THINKING_TEXT_MESSAGE_END"; thinkingId: string }
  // Tool calls
  | { type: "TOOL_CALL_START"; toolCallId: string; toolCallName: string }
  | { type: "TOOL_CALL_ARGS"; toolCallId: string; delta: string }
  | { type: "TOOL_CALL_END"; toolCallId: string }
  | { type: "TOOL_CALL_RESULT"; toolCallId: string; content: string; isError?: boolean }
  // Client-only
  | { type: "RESET" }

/** All valid StreamEvent type discriminators. Single source of truth for validation. */
export const STREAM_EVENT_TYPES: readonly StreamEvent["type"][] = [
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "TEXT_MESSAGE_START",
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_END",
  "THINKING_START",
  "THINKING_TEXT_MESSAGE_START",
  "THINKING_TEXT_MESSAGE_CONTENT",
  "THINKING_TEXT_MESSAGE_END",
  "TOOL_CALL_START",
  "TOOL_CALL_ARGS",
  "TOOL_CALL_END",
  "TOOL_CALL_RESULT",
  "RESET",
] as const

export const STREAM_EVENT_TYPE_SET: ReadonlySet<string> = new Set(STREAM_EVENT_TYPES)
