/**
 * Storybook hook that simulates AG-UI events on timers.
 *
 * Step-based: fires one event at a time, scheduling the next after dispatch.
 * This naturally supports pause/resume and live speed changes.
 */

import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from "react"

import { createInitialState, reduceStreamEvent } from "./reducer"
import type { TimelineEntry } from "./types"

export type { TimelineEntry } from "./types"

export type StreamSimulatorOptions = {
  /** Called after each event is dispatched (timer or step). Useful for external logging. */
  onEvent?: (entry: TimelineEntry, index: number) => void
}

export function useStreamSimulator(
  id: string,
  scenario: TimelineEntry[],
  speed = 1,
  options?: StreamSimulatorOptions,
) {
  const [generation, setGeneration] = useState(0)
  const [state, dispatch] = useReducer(reduceStreamEvent, id, createInitialState)
  const [paused, setPaused] = useState(false)
  const [eventIndex, setEventIndex] = useState(0)

  // Stable ref so the timer effect and step() always read the latest callback
  // without re-triggering the scheduling effect. Updated via useLayoutEffect
  // (not during render) to satisfy the react-hooks/refs lint rule.
  const onEventRef = useRef(options?.onEvent)
  useLayoutEffect(() => {
    onEventRef.current = options?.onEvent
  })

  const restart = useCallback((opts?: { preservePause?: boolean }) => {
    dispatch({ type: "RESET" })
    setEventIndex(0)
    if (!opts?.preservePause) {
      setPaused(false)
    }
    setGeneration((g) => g + 1)
  }, [])

  const togglePause = useCallback(() => {
    setPaused((p) => !p)
  }, [])

  /** Manually fire the next event without changing pause state. */
  const step = useCallback(() => {
    // Functional updater reads current index without adding eventIndex to deps,
    // which would recreate step on every advance and break memoised consumers.
    setEventIndex((currentIndex) => {
      const entry = scenario[currentIndex]
      if (!entry) return currentIndex

      dispatch(entry.event)
      onEventRef.current?.(entry, currentIndex)
      return currentIndex + 1
    })
  }, [scenario])

  // Fire one event at a time — schedule next after current dispatches
  useEffect(() => {
    if (paused || eventIndex >= scenario.length) return

    const currentDelay = scenario[eventIndex].delayMs
    const prevDelay = eventIndex > 0 ? scenario[eventIndex - 1].delayMs : 0
    const relativeDelay = Math.max(0, (currentDelay - prevDelay) / speed)

    const timer = setTimeout(() => {
      dispatch(scenario[eventIndex].event)
      onEventRef.current?.(scenario[eventIndex], eventIndex)
      setEventIndex((i) => i + 1)
    }, relativeDelay)

    return () => clearTimeout(timer)
  }, [eventIndex, paused, speed, generation, scenario])

  return {
    activity: state.activity,
    restart,
    paused,
    setPaused,
    togglePause,
    step,
    progress: { current: eventIndex, total: scenario.length },
  }
}
