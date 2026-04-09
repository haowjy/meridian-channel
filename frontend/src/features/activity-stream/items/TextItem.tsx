import ReactMarkdown from "react-markdown"

import type { ActivityItem as StreamActivityItem } from "@/features/activity-stream/streaming/reducer"

interface TextItemProps {
  item: Extract<StreamActivityItem, { type: "text" }>
}

export function TextItem({ item }: TextItemProps) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="prose prose-sm max-w-none text-foreground dark:prose-invert">
        <ReactMarkdown>{item.content}</ReactMarkdown>
      </div>
    </div>
  )
}
