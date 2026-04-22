import { AgentDetail } from "./AgentDetail"
import { BashDetail } from "./BashDetail"
import { DetailCard } from "./DetailCard"
import { EditDetail } from "./EditDetail"
import { DocSearchDetail } from "./SearchDetail"
import { getToolCategory } from "./tool-utils"
import type { ToolItem } from "./types"
import { WebSearchDetail } from "./WebSearchDetail"

type ToolDetailProps = {
  tool: ToolItem
}

/**
 * Routes a ToolItem to the appropriate detail renderer.
 *
 * Read tools return null — header + "View file" button is enough.
 * Known tools get rich rendering; everything else gets the generic
 * input → output view.
 */
export function ToolDetail({ tool }: ToolDetailProps) {
  const category = getToolCategory(tool.toolName ?? "")

  if (category === "read") {
    return null
  }

  if (category === "edit") {
    return <EditDetail tool={tool} />
  }

  if (category === "doc-search") {
    return <DocSearchDetail tool={tool} />
  }

  if (category === "web-search") {
    return <WebSearchDetail tool={tool} />
  }

  if (category === "bash") {
    return <BashDetail tool={tool} />
  }

  if (category === "agent") {
    return <AgentDetail tool={tool} />
  }

  // Generic fallback: raw input → output
  return (
    <DetailCard className="[&>div]:space-y-3 [&>div]:p-3">
      <div>
        <p className="mb-1 text-xs font-medium text-muted-foreground">Input</p>
        <pre className="overflow-auto rounded-md bg-muted/60 p-2 font-mono text-xs text-muted-foreground">
          {tool.argsText || "..."}
        </pre>
      </div>

      {tool.resultText ? (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Output</p>
          <pre className="max-h-52 overflow-auto rounded-md bg-muted/60 p-2 font-mono text-xs text-foreground/70">
            {tool.resultText}
          </pre>
        </div>
      ) : null}
    </DetailCard>
  )
}
