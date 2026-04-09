import { useMemo, useState } from "react"
import { Brain, ChevronRight } from "lucide-react"

import type { ActivityItem as StreamActivityItem } from "@/features/activity-stream/streaming/reducer"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

interface ReasoningItemProps {
  item: Extract<StreamActivityItem, { type: "reasoning" }>
}

const PREVIEW_LENGTH = 100

export function ReasoningItem({ item }: ReasoningItemProps) {
  const [open, setOpen] = useState(false)

  const preview = useMemo(() => {
    if (item.content.length <= PREVIEW_LENGTH) {
      return item.content
    }

    return `${item.content.slice(0, PREVIEW_LENGTH)}...`
  }, [item.content])

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-lg border border-border bg-muted/30"
    >
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-4 py-3 text-left">
        <ChevronRight
          className={`size-4 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`}
          aria-hidden="true"
        />
        <Brain className="size-4 text-accent-text" aria-hidden="true" />
        <span className="font-medium">Reasoning</span>
        {!open && preview ? (
          <span className="truncate text-sm text-muted-foreground">{preview}</span>
        ) : null}
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4">
        <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-card p-3 font-mono text-xs text-foreground">
          {item.content}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  )
}
