import {
  EventType,
  type StreamEvent as WsStreamEvent,
} from "@/lib/ws"

import type { StreamEvent } from "./events"

export type StartedEventSets = {
  text: Set<string>
  thinking: Set<string>
  tool: Set<string>
}

function isCancelledError(
  event: Extract<WsStreamEvent, { type: typeof EventType.RUN_ERROR }>,
) {
  if (event.code === "cancelled" || event.code === "canceled") {
    return true
  }

  return /cancelled|canceled/i.test(event.message)
}

export function mapWsEventToStreamEvents(
  event: WsStreamEvent,
  started: StartedEventSets,
): StreamEvent[] {
  const mappedEvents: StreamEvent[] = []

  switch (event.type) {
    case EventType.RUN_STARTED:
      mappedEvents.push({ type: "RUN_STARTED" })
      break
    case EventType.RUN_FINISHED:
      mappedEvents.push({ type: "RUN_FINISHED" })
      break
    case EventType.RUN_ERROR:
      mappedEvents.push({
        type: "RUN_ERROR",
        message: event.message,
        isCancelled: isCancelledError(event),
      })
      break
    case EventType.TEXT_MESSAGE_START:
      if (!started.text.has(event.messageId)) {
        started.text.add(event.messageId)
        mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.messageId })
      }
      break
    case EventType.TEXT_MESSAGE_CONTENT:
      if (!started.text.has(event.messageId)) {
        started.text.add(event.messageId)
        mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.messageId })
      }
      mappedEvents.push({
        type: "TEXT_MESSAGE_CONTENT",
        messageId: event.messageId,
        delta: event.delta,
      })
      break
    case EventType.TEXT_MESSAGE_END:
      if (started.text.has(event.messageId)) {
        mappedEvents.push({ type: "TEXT_MESSAGE_END", messageId: event.messageId })
      }
      break
    case EventType.TEXT_MESSAGE_CHUNK:
      if (!event.messageId) {
        break
      }
      if (!started.text.has(event.messageId)) {
        started.text.add(event.messageId)
        mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.messageId })
      }
      if (event.delta) {
        mappedEvents.push({
          type: "TEXT_MESSAGE_CONTENT",
          messageId: event.messageId,
          delta: event.delta,
        })
      }
      break
    case EventType.REASONING_START:
    case EventType.REASONING_MESSAGE_START:
      if (!started.thinking.has(event.messageId)) {
        started.thinking.add(event.messageId)
        mappedEvents.push({ type: "THINKING_START", thinkingId: event.messageId })
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_START",
          thinkingId: event.messageId,
        })
      }
      break
    case EventType.REASONING_MESSAGE_CONTENT:
      if (!started.thinking.has(event.messageId)) {
        started.thinking.add(event.messageId)
        mappedEvents.push({ type: "THINKING_START", thinkingId: event.messageId })
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_START",
          thinkingId: event.messageId,
        })
      }
      mappedEvents.push({
        type: "THINKING_TEXT_MESSAGE_CONTENT",
        thinkingId: event.messageId,
        delta: event.delta,
      })
      break
    case EventType.REASONING_MESSAGE_CHUNK:
      if (!event.messageId) {
        break
      }
      if (!started.thinking.has(event.messageId)) {
        started.thinking.add(event.messageId)
        mappedEvents.push({ type: "THINKING_START", thinkingId: event.messageId })
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_START",
          thinkingId: event.messageId,
        })
      }
      if (event.delta) {
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_CONTENT",
          thinkingId: event.messageId,
          delta: event.delta,
        })
      }
      break
    case EventType.REASONING_END:
    case EventType.REASONING_MESSAGE_END:
      if (started.thinking.has(event.messageId)) {
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_END",
          thinkingId: event.messageId,
        })
      }
      break
    case EventType.TOOL_CALL_START:
      if (!started.tool.has(event.toolCallId)) {
        started.tool.add(event.toolCallId)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.toolCallId,
          toolCallName: event.toolCallName,
        })
      }
      break
    case EventType.TOOL_CALL_ARGS:
      if (!started.tool.has(event.toolCallId)) {
        started.tool.add(event.toolCallId)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.toolCallId,
          toolCallName: "Tool",
        })
      }
      mappedEvents.push({
        type: "TOOL_CALL_ARGS",
        toolCallId: event.toolCallId,
        delta: event.delta,
      })
      break
    case EventType.TOOL_CALL_CHUNK:
      if (!event.toolCallId) {
        break
      }
      if (!started.tool.has(event.toolCallId)) {
        started.tool.add(event.toolCallId)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.toolCallId,
          toolCallName: event.toolCallName ?? "Tool",
        })
      }
      if (event.delta) {
        mappedEvents.push({
          type: "TOOL_CALL_ARGS",
          toolCallId: event.toolCallId,
          delta: event.delta,
        })
      }
      break
    case EventType.TOOL_CALL_END:
      if (started.tool.has(event.toolCallId)) {
        mappedEvents.push({ type: "TOOL_CALL_END", toolCallId: event.toolCallId })
      }
      break
    case EventType.TOOL_CALL_RESULT:
      if (!started.tool.has(event.toolCallId)) {
        started.tool.add(event.toolCallId)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.toolCallId,
          toolCallName: "Tool",
        })
      }
      mappedEvents.push({
        type: "TOOL_CALL_RESULT",
        toolCallId: event.toolCallId,
        content: event.content,
      })
      break
    case EventType.STEP_FINISHED:
      mappedEvents.push({ type: "RUN_FINISHED" })
      break
    default:
      break
  }

  return mappedEvents
}
