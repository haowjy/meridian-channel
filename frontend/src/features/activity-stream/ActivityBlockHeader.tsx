import { Brain, CaretDown, CaretRight, Check, CircleNotch } from "@phosphor-icons/react"

import { Badge } from "@/components/ui/badge"
import { CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"

import { getActivitySummary, getToolLineTitle } from "./tool-utils"
import type { ActivityItem } from "./types"

type ActivityBlockHeaderProps = {
  items: ActivityItem[]
  isStreaming: boolean
  isWaitingSubagents?: boolean
  expanded: boolean
  className?: string
}

export function ActivityBlockHeader({
  items,
  isStreaming,
  isWaitingSubagents = false,
  expanded,
  className,
}: ActivityBlockHeaderProps) {
  const summary = getActivitySummary(items)
  const liveSummary = getLiveActivitySummary(items)

  return (
    <CollapsibleTrigger
      className={cn(
        "flex min-h-10 w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors hover:bg-muted/40",
        className
      )}
    >
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <Brain className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="shrink-0 font-medium text-foreground">ActivityBlock:</span>
        <span className="min-w-0 truncate text-muted-foreground">
          {isWaitingSubagents ? (
            "Waiting for agents..."
          ) : isStreaming ? (
            <span className="italic">{liveSummary}</span>
          ) : (
            summary
          )}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Badge variant="secondary" className="h-5 px-2 text-[11px]">
          {isWaitingSubagents ? (
            <>
              <CircleNotch className="size-3 animate-spin" aria-hidden="true" />
              waiting
            </>
          ) : isStreaming ? (
            <>
              <CircleNotch className="size-3 animate-spin" aria-hidden="true" />
              live
            </>
          ) : (
            <>
              <Check className="size-3" aria-hidden="true" />
              done
            </>
          )}
        </Badge>
        {expanded ? (
          <CaretDown className="size-4 text-muted-foreground" aria-hidden="true" />
        ) : (
          <CaretRight className="size-4 text-muted-foreground" aria-hidden="true" />
        )}
      </div>
    </CollapsibleTrigger>
  )
}

function getLiveActivitySummary(items: ActivityItem[]): string {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index]
    if (item.kind === "tool") {
      return getToolLineTitle(item)
    }
    if (item.kind === "thinking") {
      return "Thinking..."
    }
    if (item.kind === "content" && item.text.trim()) {
      return "Writing..."
    }
  }

  return "Thinking..."
}
