import { Terminal } from "@phosphor-icons/react"

import { Badge } from "@/components/ui/badge"

import { DetailCard } from "./DetailCard"
import { readString } from "./tool-utils"
import type { ToolItem } from "./types"

type BashDetailProps = {
  tool: ToolItem
}

export function BashDetail({ tool }: BashDetailProps) {
  const command = tool.parsedArgs ? readString(tool.parsedArgs, ["command", "cmd"]) : undefined

  return (
    <DetailCard className="[&>div]:space-y-3 [&>div]:p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex min-w-0 items-center gap-2 text-sm text-foreground">
          <Terminal className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="truncate font-mono">{command ?? "..."}</span>
        </p>
        <Badge variant={tool.isError ? "destructive" : tool.status === "done" ? "success" : "secondary"}>
          {tool.status === "done" ? (tool.isError ? "error" : "exit 0") : "running"}
        </Badge>
      </div>

      {tool.resultText ? (
        <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-muted/40 p-2.5 font-mono text-xs leading-relaxed text-foreground/80">
          {tool.resultText}
        </pre>
      ) : null}
    </DetailCard>
  )
}
