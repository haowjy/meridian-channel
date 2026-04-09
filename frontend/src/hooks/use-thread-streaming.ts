import { useCallback, useEffect, useReducer, useRef, useState } from "react"

import {
  EventType,
  SpawnChannel,
  type ConnectionCapabilities,
  type StreamEvent,
} from "@/lib/ws"
import {
  initialState,
  reducer,
} from "@/features/activity-stream/streaming/reducer"

export function useThreadStreaming(spawnId: string | null) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [capabilities, setCapabilities] = useState<ConnectionCapabilities | null>(
    null,
  )
  const channelRef = useRef<SpawnChannel | null>(null)

  useEffect(() => {
    if (!spawnId) {
      channelRef.current?.destroy()
      channelRef.current = null
      setCapabilities(null)
      dispatch({ type: "RESET" })
      return
    }

    dispatch({ type: "RESET" })
    setCapabilities(null)

    const channel = new SpawnChannel(spawnId, {
      onEvent: (event: StreamEvent) => {
        if (event.type === EventType.CUSTOM && event.name === "capabilities") {
          setCapabilities(event.value as ConnectionCapabilities)
          return
        }

        dispatch(event)
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
  }, [spawnId])

  const cancel = useCallback(() => {
    const channel = channelRef.current

    if (!channel) {
      return false
    }

    const sent = channel.cancel()
    if (sent) {
      dispatch({ type: "SET_CANCELLED" })
    }

    return sent
  }, [])

  return { state, capabilities, channel: channelRef, cancel }
}
