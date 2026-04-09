import { useMemo, useState } from "react"

import type { ActivityItem as StreamActivityItem } from "@/features/activity-stream/streaming/reducer"
import { Button } from "@/components/ui/button"

interface ToolResultItemProps {
  item: Extract<StreamActivityItem, { type: "tool_result" }>
}

const MAX_PREVIEW_LENGTH = 102400

export function ToolResultItem({ item }: ToolResultItemProps) {
  const [showFull, setShowFull] = useState(false)
  const isLarge = item.content.length > MAX_PREVIEW_LENGTH

  const displayedContent = useMemo(() => {
    if (!isLarge || showFull) {
      return item.content
    }

    return `${item.content.slice(0, MAX_PREVIEW_LENGTH)}\n\n[output truncated]`
  }, [isLarge, item.content, showFull])

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/20 px-4 py-3">
      <div className="text-xs font-medium text-muted-foreground">Tool Result</div>
      <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md bg-card p-3 font-mono text-xs text-foreground">
        {displayedContent}
      </pre>
      {isLarge && !showFull ? (
        <Button variant="outline" size="sm" onClick={() => setShowFull(true)}>
          Show full output
        </Button>
      ) : null}
    </div>
  )
}
