import { CheckCircle2, Loader2 } from "lucide-react"

import type { ActivityItem as StreamActivityItem } from "@/features/activity-stream/streaming/reducer"
import { Badge } from "@/components/ui/badge"

interface ToolCallItemProps {
  item: Extract<StreamActivityItem, { type: "tool_call" }>
}

function formatArgs(args: string): string {
  const trimmed = args.trim()

  if (trimmed.length === 0) {
    return ""
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown
    return JSON.stringify(parsed, null, 2)
  } catch {
    return args
  }
}

export function ToolCallItem({ item }: ToolCallItemProps) {
  const formattedArgs = formatArgs(item.args)

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm">
          <span className="font-medium text-muted-foreground">Tool:</span>{" "}
          <code className="font-mono font-semibold text-foreground">{item.name}</code>
        </div>
        <Badge variant="outline" className="font-mono text-xs">
          {item.status === "running" ? (
            <>
              <Loader2 className="size-3 animate-spin" aria-hidden="true" /> running
            </>
          ) : (
            <>
              <CheckCircle2 className="size-3 text-success" aria-hidden="true" /> complete
            </>
          )}
        </Badge>
      </div>

      <div>
        <div className="mb-1 text-xs font-medium text-muted-foreground">Arguments</div>
        <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 font-mono text-xs text-foreground">
          {formattedArgs || "(no arguments)"}
        </pre>
      </div>
    </div>
  )
}
