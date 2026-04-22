import { Pause, Play, Rewind, SkipBack, SkipForward } from "@phosphor-icons/react"

import { MAX_SPEED, MIN_SPEED, type TimelinePlayback } from "@/lib/use-timeline-playback"
import { cn } from "@/lib/utils"

import { Badge } from "../ui/badge"
import { Button } from "../ui/button"
import { Slider } from "../ui/slider"

export type TimelineScrubberProps = {
  playback: TimelinePlayback
  /** Positions on the timeline to show marker dots */
  markers?: number[]
  /** e.g. "Event 42/180" */
  statusLabel?: string
  /** e.g. "Streaming turn 3" — shown in a badge */
  phaseLabel?: string
  className?: string
}

export function TimelineScrubber({
  playback,
  markers = [],
  statusLabel,
  phaseLabel,
  className,
}: TimelineScrubberProps) {
  const markerTrackWidth = playback.maxCursor > 0 ? playback.maxCursor : 1

  return (
    <div className={cn("mx-auto w-full max-w-4xl space-y-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={playback.rewind}
          disabled={playback.cursor === 0}
        >
          <Rewind className="size-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Rewind</span>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={playback.stepBackward}
          disabled={playback.cursor === 0}
        >
          <SkipBack className="size-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Step Back</span>
        </Button>
        <Button
          type="button"
          variant={playback.isPlaying ? "default" : "outline"}
          size="sm"
          onClick={playback.togglePlayPause}
          disabled={playback.cursor >= playback.maxCursor}
        >
          {playback.isPlaying ? (
            <Pause className="size-3.5" aria-hidden="true" />
          ) : (
            <Play className="size-3.5" aria-hidden="true" />
          )}
          <span className="hidden sm:inline">{playback.isPlaying ? "Pause" : "Play"}</span>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={playback.stepForward}
          disabled={playback.cursor >= playback.maxCursor}
        >
          <SkipForward className="size-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Step</span>
        </Button>
        <div className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
          <span className="text-xs text-muted-foreground">Speed</span>
          <Slider
            className="flex-1 sm:w-28"
            min={MIN_SPEED}
            max={MAX_SPEED}
            step={0.1}
            value={[playback.speed]}
            onValueChange={([value]) => {
              if (typeof value === "number") {
                playback.setSpeed(value)
              }
            }}
          />
          <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
            {playback.speed.toFixed(1)}x
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <div className="relative">
          <Slider
            min={0}
            max={playback.maxCursor}
            step={1}
            value={[playback.cursor]}
            onValueChange={([value]) => {
              if (typeof value === "number") {
                playback.pause()
                playback.setCursor(value)
              }
            }}
          />
          <div className="pointer-events-none absolute inset-x-2 top-1/2 -translate-y-1/2">
            {markers.map((marker, index) => (
              <span
                key={`${marker}-${index}`}
                className={cn(
                  "absolute size-2 -translate-x-1/2 rounded-full border border-background",
                  marker <= playback.cursor ? "bg-accent-fill" : "bg-muted",
                )}
                style={{
                  left: `${(marker / markerTrackWidth) * 100}%`,
                }}
              />
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {statusLabel ? <span className="font-mono tabular-nums">{statusLabel}</span> : null}
          {phaseLabel ? (
            <Badge variant="outline" className="h-5 rounded-full px-2 text-[10px] uppercase tracking-wide">
              {phaseLabel}
            </Badge>
          ) : null}
        </div>
      </div>
    </div>
  )
}
