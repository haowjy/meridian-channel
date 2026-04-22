import { useEffect, useRef, useState } from "react"

import { cn } from "@/lib/utils"

type RotatingTextProps = {
  messages: string[]
  active?: boolean
  intervalMs?: number
  fadeMs?: number
  className?: string
}

export function RotatingText({
  messages,
  active = true,
  intervalMs = 2400,
  fadeMs = 220,
  className,
}: RotatingTextProps) {
  const [index, setIndex] = useState(0)
  const [previousIndex, setPreviousIndex] = useState<number | null>(null)
  const intervalRef = useRef<number | null>(null)
  const timeoutRef = useRef<number | null>(null)

  // Reset animation indices when the messages list identity changes.
  // React's "computed state during render" pattern avoids a setState-in-effect.
  const [prevMessages, setPrevMessages] = useState(messages)
  if (prevMessages !== messages) {
    setPrevMessages(messages)
    setIndex(0)
    setPreviousIndex(null)
  }

  useEffect(() => {
    if (!active || messages.length < 2) {
      return
    }

    intervalRef.current = window.setInterval(() => {
      setIndex((current) => {
        setPreviousIndex(current)
        return (current + 1) % messages.length
      })

      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = window.setTimeout(() => {
        setPreviousIndex(null)
      }, fadeMs)
    }, intervalMs)

    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current)
      }

      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current)
      }
    }
  }, [active, fadeMs, intervalMs, messages.length])

  const currentMessage = messages[index] ?? ""
  const previousMessage = previousIndex === null ? null : messages[previousIndex]

  return (
    <span
      className={cn("relative inline-flex min-h-[1.125rem] items-center overflow-hidden", className)}
      aria-live="polite"
    >
      {previousMessage ? (
        <span className="pointer-events-none absolute inset-0 animate-out fade-out duration-200">
          {previousMessage}
        </span>
      ) : null}
      <span
        key={index}
        className={cn(previousMessage ? "animate-in fade-in duration-200" : undefined)}
      >
        {currentMessage}
      </span>
    </span>
  )
}
