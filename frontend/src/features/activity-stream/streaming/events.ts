import {
  EventType,
  type ReasoningMessageContentEvent,
  type ReasoningMessageEndEvent,
  type ReasoningMessageStartEvent,
  type RunErrorEvent,
  type RunFinishedEvent,
  type RunStartedEvent,
  type StreamEvent,
  type TextMessageContentEvent,
  type TextMessageEndEvent,
  type TextMessageStartEvent,
  type ToolCallArgsEvent,
  type ToolCallEndEvent,
  type ToolCallResultEvent,
  type ToolCallStartEvent,
} from "@/lib/ws/types"

export { EventType }

export function isRunStarted(e: StreamEvent): e is RunStartedEvent {
  return e.type === EventType.RUN_STARTED
}

export function isRunFinished(e: StreamEvent): e is RunFinishedEvent {
  return e.type === EventType.RUN_FINISHED
}

export function isRunError(e: StreamEvent): e is RunErrorEvent {
  return e.type === EventType.RUN_ERROR
}

export function isTextMessageStart(e: StreamEvent): e is TextMessageStartEvent {
  return e.type === EventType.TEXT_MESSAGE_START
}

export function isTextEvent(e: StreamEvent): e is TextMessageContentEvent {
  return e.type === EventType.TEXT_MESSAGE_CONTENT
}

export function isTextMessageEnd(e: StreamEvent): e is TextMessageEndEvent {
  return e.type === EventType.TEXT_MESSAGE_END
}

export function isReasoningMessageStart(
  e: StreamEvent,
): e is ReasoningMessageStartEvent {
  return e.type === EventType.REASONING_MESSAGE_START
}

export function isReasoningEvent(e: StreamEvent): e is ReasoningMessageContentEvent {
  return e.type === EventType.REASONING_MESSAGE_CONTENT
}

export function isReasoningMessageEnd(e: StreamEvent): e is ReasoningMessageEndEvent {
  return e.type === EventType.REASONING_MESSAGE_END
}

export function isToolCallStart(e: StreamEvent): e is ToolCallStartEvent {
  return e.type === EventType.TOOL_CALL_START
}

export function isToolCallArgs(e: StreamEvent): e is ToolCallArgsEvent {
  return e.type === EventType.TOOL_CALL_ARGS
}

export function isToolCallEnd(e: StreamEvent): e is ToolCallEndEvent {
  return e.type === EventType.TOOL_CALL_END
}

export function isToolCallResult(e: StreamEvent): e is ToolCallResultEvent {
  return e.type === EventType.TOOL_CALL_RESULT
}
