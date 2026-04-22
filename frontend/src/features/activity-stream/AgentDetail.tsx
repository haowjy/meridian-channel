import { useActivityNesting } from "./activity-context"
import { DetailCard } from "./DetailCard"
import { readString } from "./tool-utils"
import type { ToolItem } from "./types"

type AgentDetailProps = {
  tool: ToolItem
}

export function AgentDetail({ tool }: AgentDetailProps) {
  const { depth, renderNestedActivity } = useActivityNesting()
  const agentName = tool.parsedArgs
    ? readString(tool.parsedArgs, ["name", "description", "prompt"])
    : undefined

  return (
    <div className="space-y-2">
      <DetailCard accent className="[&>div]:p-3">
        {tool.nestedActivity ? (
          renderNestedActivity(tool.nestedActivity, depth + 1)
        ) : (
          <p className="text-xs text-muted-foreground">
            {tool.status === "executing"
              ? `${agentName ?? "Agent"} working...`
              : "No activity"}
          </p>
        )}
      </DetailCard>

      {tool.resultText ? (
        <p className="text-sm text-muted-foreground">{tool.resultText}</p>
      ) : null}
    </div>
  )
}
