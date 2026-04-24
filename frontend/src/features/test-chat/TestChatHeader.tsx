import { Info, Pause, Square } from "lucide-react"

import { MonoId, StatusDot } from "@/components/atoms"
import { ThemeToggle } from "@/components/ui/theme-toggle"
import { Button } from "@/components/ui/button"
import { Popover, PopoverTrigger } from "@/components/ui/popover"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ConnectionCapabilities, WsState } from "@/lib/ws"
import type { SpawnStatus } from "@/types/spawn"
import { cn } from "@/lib/utils"

import type { TestChatSessionInfo } from "./session-api"
import { SessionDebugPopover } from "./SessionDebugPopover"

interface TestChatHeaderProps {
  session: TestChatSessionInfo
  connectionState: WsState
  capabilities: ConnectionCapabilities | null
  isStreaming: boolean
  sessionEnded: boolean
  onInterrupt: () => void
  onCancel: () => void
}

function getStatus(connectionState: WsState, sessionEnded: boolean): SpawnStatus {
  if (sessionEnded) {
    return "succeeded"
  }
  if (connectionState === "open") {
    return "running"
  }
  if (connectionState === "connecting") {
    return "queued"
  }
  return "cancelled"
}

export function TestChatHeader({
  session,
  connectionState,
  capabilities,
  isStreaming,
  sessionEnded,
  onInterrupt,
  onCancel,
}: TestChatHeaderProps) {
  const status = getStatus(connectionState, sessionEnded)
  const modelLabel = session.model || "unknown"
  const canControl = !sessionEnded && connectionState === "open"

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur">
      <StatusDot status={status} size="sm" />
      <MonoId id={session.spawn_id} copyable />
      <span className="text-xs text-muted-foreground">{session.harness}</span>
      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">
        {modelLabel}
      </span>
      <span
        className={cn(
          "text-xs",
          connectionState === "open" ? "text-muted-foreground" : "text-destructive",
        )}
      >
        {sessionEnded
          ? "session ended"
          : connectionState === "closed" || connectionState === "closing"
            ? "disconnected"
            : connectionState}
      </span>
      {isStreaming ? (
        <span className="rounded-full border border-accent-fill/30 bg-accent-fill/10 px-2 py-0.5 text-[11px] text-accent-text">
          streaming
        </span>
      ) : null}

      <div className="flex-1" />

      {canControl && isStreaming ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-8"
              onClick={onInterrupt}
              aria-label="Interrupt current turn"
            >
              <Pause className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Interrupt</TooltipContent>
        </Tooltip>
      ) : null}

      {canControl ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={onCancel}
              aria-label="Cancel spawn"
            >
              <Square className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Cancel spawn</TooltipContent>
        </Tooltip>
      ) : null}

      <Popover>
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="size-8"
                aria-label="Show session details"
              >
                <Info className="size-4" />
              </Button>
            </PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent>Session details</TooltipContent>
        </Tooltip>
        <SessionDebugPopover
          session={session}
          connectionState={connectionState}
          capabilities={capabilities}
        />
      </Popover>

      <ThemeToggle />
    </header>
  )
}
