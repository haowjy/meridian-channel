import { DetailCard } from "./DetailCard"
import { readString } from "./tool-utils"
import type { ToolItem } from "./types"

type DocSearchDetailProps = {
  tool: ToolItem
}

export function DocSearchDetail({ tool }: DocSearchDetailProps) {
  const query = tool.parsedArgs ? readString(tool.parsedArgs, ["pattern", "query", "search"]) : undefined

  return (
    <DetailCard className="[&>div]:space-y-2 [&>div]:p-3">
      {tool.resultText ? (
        <pre className="max-h-52 overflow-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
          {tool.resultText}
        </pre>
      ) : (
        <p className="text-sm text-muted-foreground">
          {tool.status === "executing"
            ? `Searching for ${query ? `"${query}"` : "..."}...`
            : "No results"}
        </p>
      )}
    </DetailCard>
  )
}
