import { useCallback, useMemo, useState } from "react"

import type { Meta, StoryObj } from "@storybook/react-vite"

import { TimelineScrubber } from "@/components/storybook/TimelineScrubber"
import { useTimelinePlayback } from "@/lib/use-timeline-playback"

import { ActivityBlock } from "./ActivityBlock"
import { PACING_FIX_SCENARIO } from "./examples/streaming-scenario"
import { STREAM_EVENT_TYPE_SET } from "./streaming/events"
import type { StreamEvent } from "./streaming/events"
import { createInitialState, reduceStreamEvent } from "./streaming/reducer"
import type { TimelineEntry } from "./streaming/types"
import type { ActivityBlockData } from "./types"

type TimelineParseResult =
  | { ok: true; timeline: TimelineEntry[] }
  | { ok: false; error: string }

type EventLogEntry = {
  sequence: number
  delayMs: number
  type: StreamEvent["type"]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function serializeTimeline(timeline: TimelineEntry[]): string {
  return JSON.stringify(timeline, null, 2)
}

function parseTimelineText(value: string): TimelineParseResult {
  let parsed: unknown

  try {
    parsed = JSON.parse(value)
  } catch {
    return { ok: false, error: "Timeline must be valid JSON." }
  }

  if (!Array.isArray(parsed)) {
    return { ok: false, error: "Timeline must be a JSON array of { delayMs, event } entries." }
  }

  const timeline: TimelineEntry[] = []

  for (let index = 0; index < parsed.length; index += 1) {
    const entry = parsed[index]
    if (!isRecord(entry)) {
      return { ok: false, error: `Entry ${index + 1} must be an object.` }
    }

    const delayMs = entry.delayMs
    const event = entry.event

    if (typeof delayMs !== "number" || !Number.isFinite(delayMs) || delayMs < 0) {
      return { ok: false, error: `Entry ${index + 1} has invalid delayMs.` }
    }

    if (!isRecord(event) || typeof event.type !== "string") {
      return { ok: false, error: `Entry ${index + 1} has invalid event.` }
    }

    if (!STREAM_EVENT_TYPE_SET.has(event.type)) {
      return { ok: false, error: `Entry ${index + 1} uses unknown event.type "${event.type}".` }
    }

    if (index > 0) {
      const previousDelayMs = timeline[index - 1]?.delayMs ?? 0
      if (delayMs < previousDelayMs) {
        return {
          ok: false,
          error: `Entry ${index + 1} delayMs must be >= entry ${index} delayMs.`,
        }
      }
    }

    timeline.push({
      delayMs,
      event: event as StreamEvent,
    })
  }

  return { ok: true, timeline }
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const millis = Math.floor(ms % 1000)

  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}.${millis
    .toString()
    .padStart(3, "0")}`
}

function buildActivityAtCursor(id: string, timeline: TimelineEntry[], cursor: number): ActivityBlockData {
  const clampedCursor = Math.min(Math.max(cursor, 0), timeline.length)
  const entries = timeline.slice(0, clampedCursor)
  let state = createInitialState(id)
  for (const entry of entries) {
    state = reduceStreamEvent(state, entry.event)
  }
  return state.activity
}

const meta = {
  title: "Features/Threads/Activity Block/Streaming Editor",
  component: ActivityBlock,
  args: { activity: { id: "default", items: [] } },
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<typeof ActivityBlock>

export default meta
type Story = StoryObj<typeof meta>

export const StreamingEditor: Story = {
  render: function StreamingEditorStory() {
    const initialTimelineText = useMemo(() => serializeTimeline(PACING_FIX_SCENARIO), [])
    const [editorValue, setEditorValue] = useState(initialTimelineText)
    const [timeline, setTimeline] = useState(PACING_FIX_SCENARIO)
    const [parseError, setParseError] = useState<string | null>(null)

    const getDelayMs = useCallback(
      (currentStep: number, speed: number) => {
        if (currentStep <= 0) return 0
        const current = timeline[currentStep]?.delayMs ?? 0
        const previous = currentStep > 0 ? (timeline[currentStep - 1]?.delayMs ?? 0) : 0
        return Math.max(0, (current - previous) / speed)
      },
      [timeline],
    )

    const playback = useTimelinePlayback({
      totalSteps: timeline.length,
      getDelayMs,
      autoplay: true,
      initialSpeed: 1,
    })

    const cursor = Math.min(playback.cursor, timeline.length)

    const replaceTimeline = useCallback(
      (nextTimeline: TimelineEntry[]) => {
        setTimeline(nextTimeline)
        playback.rewind()
      },
      [playback],
    )

    const activity = useMemo(
      () => buildActivityAtCursor("streaming-editor", timeline, cursor),
      [cursor, timeline],
    )

    const eventLog = useMemo<EventLogEntry[]>(
      () =>
        timeline.slice(0, cursor).map((entry, index) => ({
          sequence: index + 1,
          delayMs: entry.delayMs,
          type: entry.event.type,
        })),
      [timeline, cursor],
    )

    const phaseLabel = useMemo(() => {
      if (parseError) return "Invalid"
      if (activity.error) return "Error"
      if (activity.isStreaming) return "Streaming"
      if (cursor >= timeline.length) return "Complete"
      return "Ready"
    }, [activity.error, activity.isStreaming, cursor, parseError, timeline.length])

    const onEditorChange = useCallback(
      (nextValue: string) => {
        setEditorValue(nextValue)

        const parsed = parseTimelineText(nextValue)
        if (!parsed.ok) {
          setParseError(parsed.error)
          return
        }

        setParseError(null)
        replaceTimeline(parsed.timeline)
      },
      [replaceTimeline],
    )

    return (
      <div className="h-full min-h-screen overflow-x-hidden bg-background px-2 py-4 font-mono sm:px-4 md:px-6">
        <div className="mx-auto max-w-[1440px] space-y-4">
          <div className="rounded-md border border-border bg-card p-3">
            <TimelineScrubber
              playback={playback}
              statusLabel={`Event ${cursor}/${timeline.length}`}
              phaseLabel={phaseLabel}
            />
          </div>

          <div className="grid gap-2 sm:gap-4 lg:grid-cols-2">
            <section className="order-last min-w-0 rounded-md border border-border bg-card p-3 lg:order-none">
              <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                Timeline Editor (JSON from scenario.ts)
              </div>
              <textarea
                value={editorValue}
                onChange={(event) => onEditorChange(event.target.value)}
                spellCheck={false}
                className="h-[560px] w-full resize-none rounded border border-border bg-background p-3 font-mono text-xs leading-5"
              />
              <div className="mt-2 text-xs">
                {parseError ? (
                  <span className="text-destructive">{parseError}</span>
                ) : (
                  <span className="text-muted-foreground">
                    Valid timeline loaded. Changes replay immediately from the start.
                  </span>
                )}
              </div>
            </section>

            <section className="order-first min-w-0 lg:order-none lg:rounded-md lg:border lg:border-border lg:bg-card lg:p-3">
              <div className="mb-2 hidden text-xs uppercase tracking-wide text-muted-foreground lg:block">
                Live ActivityBlock Output
              </div>
              <ActivityBlock activity={activity} defaultExpanded />
            </section>
          </div>

          <section className="rounded-md border border-border bg-card p-3">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Event Log
            </div>
            {eventLog.length === 0 ? (
              <p className="text-xs text-muted-foreground">No events fired yet.</p>
            ) : (
              <ul className="max-h-64 space-y-1 overflow-y-auto rounded border border-border bg-background p-2 text-xs">
                {eventLog.map((entry) => (
                  <li
                    key={entry.sequence}
                    className="grid grid-cols-[110px_160px_1fr] gap-3 border-b border-border/40 pb-1 last:border-b-0"
                  >
                    <span className="text-muted-foreground">{formatElapsed(entry.delayMs)}</span>
                    <span className="text-muted-foreground">delay {entry.delayMs}ms</span>
                    <span className="text-foreground">{entry.type}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    )
  },
}
