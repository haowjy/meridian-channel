/**
 * SpawnHeader — compact per-column header for a spawn in chat mode.
 *
 * Shows identity (status dot, spawn id, agent, model) on the left and
 * streaming controls (interrupt, cancel) plus a close-column button on
 * the right. Designed to sit above SpawnActivityView inside ThreadColumn
 * at a fixed 36px height so multiple columns line up visually.
 *
 * The header never drives its own data — it's a pure presentational slice
 * that receives spawn identity + callbacks from ThreadColumn. Button
 * affordances follow the Composer convention: Pause (interrupt) while
 * streaming, Square (cancel) for any non-terminal spawn, X (close column)
 * always available.
 */
import { Pause, Square, X } from "@phosphor-icons/react"

import { MonoId, StatusDot } from "@/components/atoms"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { SpawnStatus } from "@/types/spawn"
import { cn } from "@/lib/utils"

export interface SpawnHeaderProps {
  spawnId: string
  status: SpawnStatus
  agent: string | null
  model: string | null
  harness: string
  isStreaming: boolean
  onInterrupt?: () => void
  onCancel?: () => void
  onClose?: () => void
  className?: string
}

const TERMINAL_STATUSES: ReadonlySet<SpawnStatus> = new Set<SpawnStatus>([
  "succeeded",
  "failed",
  "cancelled",
])

export function SpawnHeader({
  spawnId,
  status,
  agent,
  model,
  harness,
  isStreaming,
  onInterrupt,
  onCancel,
  onClose,
  className,
}: SpawnHeaderProps) {
  const canCancel =
    !TERMINAL_STATUSES.has(status) &&
    (status === "running" || status === "queued" || status === "finalizing")

  const modelLabel = model ?? harness

  return (
    <div
      className={cn(
        "flex h-9 shrink-0 items-center gap-2 border-b border-border",
        "bg-muted/30 px-3 text-xs",
        className,
      )}
    >
      <StatusDot status={status} size="sm" />

      <MonoId id={spawnId} copyable />

      {agent ? (
        <span className="truncate text-muted-foreground" title={agent}>
          {agent}
        </span>
      ) : (
        <span className="italic text-muted-foreground/70">no agent</span>
      )}

      {modelLabel ? (
        <span
          className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground"
          title={model ? `model: ${model}` : `harness: ${harness}`}
        >
          {modelLabel}
        </span>
      ) : null}

      <div className="flex-1" />

      {isStreaming && onInterrupt ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-6"
              onClick={onInterrupt}
              aria-label="Interrupt current turn"
            >
              <Pause className="size-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={4}>
            Interrupt
          </TooltipContent>
        </Tooltip>
      ) : null}

      {canCancel && onCancel ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-6 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={onCancel}
              aria-label="Cancel spawn"
            >
              <Square className="size-3.5" weight="fill" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={4}>
            Cancel spawn
          </TooltipContent>
        </Tooltip>
      ) : null}

      {onClose ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-6 text-muted-foreground"
              onClick={onClose}
              aria-label="Close column"
            >
              <X className="size-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={4}>
            Close column
          </TooltipContent>
        </Tooltip>
      ) : null}
    </div>
  )
}
