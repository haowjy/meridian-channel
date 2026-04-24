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
import { mapWsEventToStreamEvents } from "@/features/activity-stream/streaming/map-ws-event"
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
      const mappedEvents = mapWsEventToStreamEvents(event, {
        text: startedTextRef.current,
        thinking: startedThinkingRef.current,
        tool: startedToolRef.current,
      })

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
