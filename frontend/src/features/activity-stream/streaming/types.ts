import type { StreamEvent } from "./events"

export type TimelineEntry = {
  /** Absolute milliseconds from the start of the simulation. */
  delayMs: number
  event: StreamEvent
}
