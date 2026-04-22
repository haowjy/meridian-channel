import { Globe } from "@phosphor-icons/react"

import { DetailCard } from "./DetailCard"
import { readString } from "./tool-utils"
import type { ToolItem } from "./types"

type WebSearchDetailProps = {
  tool: ToolItem
}

export function WebSearchDetail({ tool }: WebSearchDetailProps) {
  const query = tool.parsedArgs ? readString(tool.parsedArgs, ["query", "search_query", "q"]) : undefined

  return (
    <DetailCard className="[&>div]:space-y-2 [&>div]:p-3">
      {tool.resultText ? (
        <pre className="max-h-52 overflow-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
          {tool.resultText}
        </pre>
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Globe className="size-3.5 shrink-0" aria-hidden="true" />
          {tool.status === "executing"
            ? `Searching for ${query ? `"${query}"` : "..."}...`
            : "No results"}
        </p>
      )}
    </DetailCard>
  )
}
