import { useCallback, useEffect, useReducer, useRef, useState } from "react"

import {
  EventType,
  SpawnChannel,
  type ConnectionCapabilities,
  type StreamEvent as WsStreamEvent,
  type WsState,
} from "@/lib/ws"
import {
  createInitialState,
  reduceStreamEvent,
} from "@/features/activity-stream/streaming/reducer"
import type { StreamEvent } from "@/features/activity-stream/streaming/events"
import type { ActivityBlockData } from "@/features/activity-stream/types"

type StreamAction =
  | StreamEvent
  | {
      type: "RESET_WITH_ID"
      id: string
    }

function streamingReducer(
  state: ReturnType<typeof createInitialState>,
  action: StreamAction,
) {
  if (action.type === "RESET_WITH_ID") {
    return createInitialState(action.id)
  }

  return reduceStreamEvent(state, action)
}

function isCancelledError(event: Extract<WsStreamEvent, { type: typeof EventType.RUN_ERROR }>) {
  if (event.code === "cancelled" || event.code === "canceled") {
    return true
  }

  return /cancelled|canceled/i.test(event.message)
}

export function useThreadStreaming(spawnId: string | null) {
  const [streamState, dispatch] = useReducer(streamingReducer, createInitialState("idle"))
  const [capabilities, setCapabilities] = useState<ConnectionCapabilities | null>(
    null,
  )
  const [connectionState, setConnectionState] = useState<WsState>("idle")
  const channelRef = useRef<SpawnChannel | null>(null)
  const startedTextRef = useRef<Set<string>>(new Set())
  const startedThinkingRef = useRef<Set<string>>(new Set())
  const startedToolRef = useRef<Set<string>>(new Set())

  const dispatchMappedEvent = useCallback(
    (event: WsStreamEvent) => {
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
          if (!startedTextRef.current.has(event.message_id)) {
            startedTextRef.current.add(event.message_id)
            mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.message_id })
          }
          break
        case EventType.TEXT_MESSAGE_CONTENT:
          if (!startedTextRef.current.has(event.message_id)) {
            startedTextRef.current.add(event.message_id)
            mappedEvents.push({ type: "TEXT_MESSAGE_START", messageId: event.message_id })
          }
          mappedEvents.push({
            type: "TEXT_MESSAGE_CONTENT",
            messageId: event.message_id,
            delta: event.delta,
          })
          break
        case EventType.TEXT_MESSAGE_END:
          if (startedTextRef.current.has(event.message_id)) {
            mappedEvents.push({ type: "TEXT_MESSAGE_END", messageId: event.message_id })
          }
          break
        case EventType.TEXT_MESSAGE_CHUNK:
          if (!event.message_id) {
            break
          }
          if (!startedTextRef.current.has(event.message_id)) {
            startedTextRef.current.add(event.message_id)
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
          if (!startedThinkingRef.current.has(event.message_id)) {
            startedThinkingRef.current.add(event.message_id)
            mappedEvents.push({ type: "THINKING_START", thinkingId: event.message_id })
            mappedEvents.push({ type: "THINKING_TEXT_MESSAGE_START", thinkingId: event.message_id })
          }
          break
        case EventType.REASONING_MESSAGE_CONTENT:
          if (!startedThinkingRef.current.has(event.message_id)) {
            startedThinkingRef.current.add(event.message_id)
            mappedEvents.push({ type: "THINKING_START", thinkingId: event.message_id })
            mappedEvents.push({ type: "THINKING_TEXT_MESSAGE_START", thinkingId: event.message_id })
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
          if (!startedThinkingRef.current.has(event.message_id)) {
            startedThinkingRef.current.add(event.message_id)
            mappedEvents.push({ type: "THINKING_START", thinkingId: event.message_id })
            mappedEvents.push({ type: "THINKING_TEXT_MESSAGE_START", thinkingId: event.message_id })
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
          if (startedThinkingRef.current.has(event.message_id)) {
            mappedEvents.push({ type: "THINKING_TEXT_MESSAGE_END", thinkingId: event.message_id })
          }
          break
        case EventType.TOOL_CALL_START:
          if (!startedToolRef.current.has(event.tool_call_id)) {
            startedToolRef.current.add(event.tool_call_id)
            mappedEvents.push({
              type: "TOOL_CALL_START",
              toolCallId: event.tool_call_id,
              toolCallName: event.tool_call_name,
            })
          }
          break
        case EventType.TOOL_CALL_ARGS:
          if (!startedToolRef.current.has(event.tool_call_id)) {
            startedToolRef.current.add(event.tool_call_id)
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
          if (!startedToolRef.current.has(event.tool_call_id)) {
            startedToolRef.current.add(event.tool_call_id)
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
          if (startedToolRef.current.has(event.tool_call_id)) {
            mappedEvents.push({ type: "TOOL_CALL_END", toolCallId: event.tool_call_id })
          }
          break
        case EventType.TOOL_CALL_RESULT:
          if (!startedToolRef.current.has(event.tool_call_id)) {
            startedToolRef.current.add(event.tool_call_id)
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
          // Codex emits STEP_FINISHED at turn completion. In single-spawn mode,
          // this signals the activity is done, so dispatch RUN_FINISHED to clear
          // isStreaming state.
          mappedEvents.push({ type: "RUN_FINISHED" })
          break
        default:
          break
      }

      for (const nextEvent of mappedEvents) {
        dispatch(nextEvent)
      }
    },
    [],
  )

  useEffect(() => {
    if (!spawnId) {
      channelRef.current?.destroy()
      channelRef.current = null
      setCapabilities(null)
      setConnectionState("idle")
      startedTextRef.current.clear()
      startedThinkingRef.current.clear()
      startedToolRef.current.clear()
      dispatch({ type: "RESET_WITH_ID", id: "idle" })
      return
    }

    startedTextRef.current.clear()
    startedThinkingRef.current.clear()
    startedToolRef.current.clear()
    dispatch({ type: "RESET_WITH_ID", id: spawnId })
    setCapabilities(null)
    setConnectionState("connecting")

    const channel = new SpawnChannel(spawnId, {
      onEvent: (event: WsStreamEvent) => {
        if (event.type === EventType.CUSTOM && event.name === "capabilities") {
          setCapabilities(event.value as ConnectionCapabilities)
          return
        }

        dispatchMappedEvent(event)
      },
      onStateChange: (nextState: WsState) => {
        setConnectionState(nextState)
      },
    })

    channel.connect()
    channelRef.current = channel

    return () => {
      channel.destroy()

      if (channelRef.current === channel) {
        channelRef.current = null
      }
    }
  }, [dispatchMappedEvent, spawnId])

  const cancel = useCallback(() => {
    const channel = channelRef.current

    if (!channel) {
      return false
    }

    const sent = channel.cancel()
    return sent
  }, [])

  const state: ActivityBlockData = streamState.activity

  return { state, capabilities, channel: channelRef, cancel, connectionState }
}
