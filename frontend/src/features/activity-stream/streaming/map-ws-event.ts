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
      if (!started.text.has(event.message_id)) {
        started.text.add(event.message_id)
        mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.message_id })
      }
      break
    case EventType.TEXT_MESSAGE_CONTENT:
      if (!started.text.has(event.message_id)) {
        started.text.add(event.message_id)
        mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.message_id })
      }
      mappedEvents.push({
        type: "TEXT_MESSAGE_CONTENT",
        messageId: event.message_id,
        delta: event.delta,
      })
      break
    case EventType.TEXT_MESSAGE_END:
      if (started.text.has(event.message_id)) {
        mappedEvents.push({ type: "TEXT_MESSAGE_END", messageId: event.message_id })
      }
      break
    case EventType.TEXT_MESSAGE_CHUNK:
      if (!event.message_id) {
        break
      }
      if (!started.text.has(event.message_id)) {
        started.text.add(event.message_id)
        mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.message_id })
      }
      if (event.delta) {
        mappedEvents.push({
          type: "TEXT_MESSAGE_CONTENT",
          messageId: event.message_id,
          delta: event.delta,
        })
      }
      break
    case EventType.REASONING_START:
    case EventType.REASONING_MESSAGE_START:
      if (!started.thinking.has(event.message_id)) {
        started.thinking.add(event.message_id)
        mappedEvents.push({ type: "THINKING_START", thinkingId: event.message_id })
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_START",
          thinkingId: event.message_id,
        })
      }
      break
    case EventType.REASONING_MESSAGE_CONTENT:
      if (!started.thinking.has(event.message_id)) {
        started.thinking.add(event.message_id)
        mappedEvents.push({ type: "THINKING_START", thinkingId: event.message_id })
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_START",
          thinkingId: event.message_id,
        })
      }
      mappedEvents.push({
        type: "THINKING_TEXT_MESSAGE_CONTENT",
        thinkingId: event.message_id,
        delta: event.delta,
      })
      break
    case EventType.REASONING_MESSAGE_CHUNK:
      if (!event.message_id) {
        break
      }
      if (!started.thinking.has(event.message_id)) {
        started.thinking.add(event.message_id)
        mappedEvents.push({ type: "THINKING_START", thinkingId: event.message_id })
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_START",
          thinkingId: event.message_id,
        })
      }
      if (event.delta) {
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_CONTENT",
          thinkingId: event.message_id,
          delta: event.delta,
        })
      }
      break
    case EventType.REASONING_END:
    case EventType.REASONING_MESSAGE_END:
      if (started.thinking.has(event.message_id)) {
        mappedEvents.push({
          type: "THINKING_TEXT_MESSAGE_END",
          thinkingId: event.message_id,
        })
      }
      break
    case EventType.TOOL_CALL_START:
      if (!started.tool.has(event.tool_call_id)) {
        started.tool.add(event.tool_call_id)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.tool_call_id,
          toolCallName: event.tool_call_name,
        })
      }
      break
    case EventType.TOOL_CALL_ARGS:
      if (!started.tool.has(event.tool_call_id)) {
        started.tool.add(event.tool_call_id)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.tool_call_id,
          toolCallName: "Tool",
        })
      }
      mappedEvents.push({
        type: "TOOL_CALL_ARGS",
        toolCallId: event.tool_call_id,
        delta: event.delta,
      })
      break
    case EventType.TOOL_CALL_CHUNK:
      if (!event.tool_call_id) {
        break
      }
      if (!started.tool.has(event.tool_call_id)) {
        started.tool.add(event.tool_call_id)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.tool_call_id,
          toolCallName: event.tool_call_name ?? "Tool",
        })
      }
      if (event.delta) {
        mappedEvents.push({
          type: "TOOL_CALL_ARGS",
          toolCallId: event.tool_call_id,
          delta: event.delta,
        })
      }
      break
    case EventType.TOOL_CALL_END:
      if (started.tool.has(event.tool_call_id)) {
        mappedEvents.push({ type: "TOOL_CALL_END", toolCallId: event.tool_call_id })
      }
      break
    case EventType.TOOL_CALL_RESULT:
      if (!started.tool.has(event.tool_call_id)) {
        started.tool.add(event.tool_call_id)
        mappedEvents.push({
          type: "TOOL_CALL_START",
          toolCallId: event.tool_call_id,
          toolCallName: "Tool",
        })
      }
      mappedEvents.push({
        type: "TOOL_CALL_RESULT",
        toolCallId: event.tool_call_id,
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
