import type { ActivityItem as StreamActivityItem } from "@/features/activity-stream/streaming/reducer"

import { ErrorItem } from "./ErrorItem"
import { ReasoningItem } from "./ReasoningItem"
import { TextItem } from "./TextItem"
import { ToolCallItem } from "./ToolCallItem"
import { ToolResultItem } from "./ToolResultItem"

interface ActivityItemProps {
  item: StreamActivityItem
}

export function ActivityItem({ item }: ActivityItemProps) {
  switch (item.type) {
    case "text":
      return <TextItem item={item} />

    case "reasoning":
      return <ReasoningItem item={item} />

    case "tool_call":
      return <ToolCallItem item={item} />

    case "tool_result":
      return <ToolResultItem item={item} />

    case "error":
      return <ErrorItem message={item.message} />

    default:
      return null
  }
}
