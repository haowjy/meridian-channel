import { useEffect, useRef } from "react"

import type { ActivityItem as StreamActivityItem } from "@/features/activity-stream/streaming/reducer"
import { ActivityItem } from "@/features/activity-stream/items/ActivityItem"
import { ErrorItem } from "@/features/activity-stream/items/ErrorItem"
import { ScrollArea } from "@/components/ui/scroll-area"

interface ThreadViewProps {
  items: StreamActivityItem[]
  error: string | null
}

function getItemKey(item: StreamActivityItem, index: number): string {
  switch (item.type) {
    case "text":
      return `text:${item.messageId}:${index}`

    case "reasoning":
      return `reasoning:${item.messageId}:${index}`

    case "tool_call":
      return `tool_call:${item.toolCallId}:${index}`

    case "tool_result":
      return `tool_result:${item.toolCallId}:${index}`

    case "error":
      return `error:${index}`

    default:
      return `item:${index}`
  }
}

export function ThreadView({ items, error }: ThreadViewProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [items, error])

  return (
    <ScrollArea className="h-full rounded-lg border border-border bg-card">
      <div className="space-y-3 p-4">
        {items.map((item, index) => (
          <ActivityItem key={getItemKey(item, index)} item={item} />
        ))}
        {error ? <ErrorItem message={error} /> : null}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
