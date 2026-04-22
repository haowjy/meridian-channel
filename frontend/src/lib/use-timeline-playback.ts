import { useCallback, useEffect, useState } from "react"

export const MIN_SPEED = 0.1
export const MAX_SPEED = 4

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export type TimelinePlaybackConfig = {
  /** Total number of steps (0 to totalSteps inclusive) */
  totalSteps: number
  /** Delay in ms before advancing from `currentStep` to the next. Return 0 for instant. */
  getDelayMs: (currentStep: number, speed: number) => number
  autoplay?: boolean
  initialSpeed?: number
}

export type TimelinePlayback = {
  cursor: number
  maxCursor: number
  speed: number
  isPlaying: boolean
  setCursor: (next: number) => void
  setSpeed: (next: number) => void
  play: () => void
  pause: () => void
  togglePlayPause: () => void
  stepForward: () => void
  stepBackward: () => void
  rewind: () => void
  restart: () => void
}

export function useTimelinePlayback(config: TimelinePlaybackConfig): TimelinePlayback {
  const maxCursor = Math.max(0, config.totalSteps)
  const getDelayMs = config.getDelayMs

  const [cursor, setCursorState] = useState(0)
  const [isPlaying, setIsPlaying] = useState(Boolean(config.autoplay))
  const [speed, setSpeedState] = useState(clamp(config.initialSpeed ?? 1, MIN_SPEED, MAX_SPEED))

  const setCursor = useCallback(
    (nextCursor: number) => {
      setCursorState(clamp(nextCursor, 0, maxCursor))
    },
    [maxCursor],
  )

  const setSpeed = useCallback((nextSpeed: number) => {
    setSpeedState(clamp(nextSpeed, MIN_SPEED, MAX_SPEED))
  }, [])

  useEffect(() => {
    if (!isPlaying) {
      return
    }

    if (cursor >= maxCursor) {
      return
    }

    const nextCursor = cursor + 1
    const delayMs = getDelayMs(cursor, speed)
    const timer = setTimeout(() => {
      setCursorState(nextCursor)
      if (nextCursor >= maxCursor) {
        setIsPlaying(false)
      }
    }, delayMs)

    return () => {
      clearTimeout(timer)
    }
  }, [cursor, getDelayMs, isPlaying, maxCursor, speed])

  const play = useCallback(() => {
    setIsPlaying(true)
  }, [])

  const pause = useCallback(() => {
    setIsPlaying(false)
  }, [])

  const togglePlayPause = useCallback(() => {
    setIsPlaying((current) => !current)
  }, [])

  const stepForward = useCallback(() => {
    setIsPlaying(false)
    setCursorState((current) => clamp(current + 1, 0, maxCursor))
  }, [maxCursor])

  const stepBackward = useCallback(() => {
    setIsPlaying(false)
    setCursorState((current) => clamp(current - 1, 0, maxCursor))
  }, [maxCursor])

  const rewind = useCallback(() => {
    setIsPlaying(false)
    setCursorState(0)
  }, [])

  const restart = useCallback(() => {
    setCursorState(0)
    setIsPlaying(true)
  }, [])

  return {
    cursor,
    maxCursor,
    speed,
    isPlaying,
    setCursor,
    setSpeed,
    play,
    pause,
    togglePlayPause,
    stepForward,
    stepBackward,
    rewind,
    restart,
  }
}
