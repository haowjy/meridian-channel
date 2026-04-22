import { useMemo } from "react"

import { cn } from "@/lib/utils"

import { DetailCard } from "./DetailCard"
import { readString } from "./tool-utils"
import type { DiffLine, ToolItem } from "./types"

type EditDetailProps = {
  tool: ToolItem
}

function computeDiff(oldStr?: string, newStr?: string) {
  const lines: DiffLine[] = []
  let added = 0
  let removed = 0

  if (oldStr) {
    for (const line of oldStr.split("\n")) {
      lines.push({ type: "remove", text: line })
      removed++
    }
  }

  if (newStr) {
    for (const line of newStr.split("\n")) {
      lines.push({ type: "add", text: line })
      added++
    }
  }

  return { lines, added, removed }
}

export function EditDetail({ tool }: EditDetailProps) {
  const oldString = tool.parsedArgs ? readString(tool.parsedArgs, ["old_string", "old_str"]) : undefined
  const newString = tool.parsedArgs ? readString(tool.parsedArgs, ["new_string", "new_str"]) : undefined

  const { lines: diffLines, added: addedLines, removed: removedLines } = useMemo(
    () => computeDiff(oldString, newString),
    [oldString, newString],
  )

  if (diffLines.length === 0) {
    return (
      <DetailCard>
        <p className="text-xs text-muted-foreground">
          {tool.status === "streaming-args" ? "Streaming edit..." : "No changes"}
        </p>
      </DetailCard>
    )
  }

  return (
    <DetailCard className="[&>div]:space-y-2 [&>div]:p-3">
      <p className="text-xs text-muted-foreground">
        +{addedLines} lines, -{removedLines} lines
      </p>

      <pre className="max-h-52 overflow-auto rounded-md bg-muted/40 font-mono text-xs leading-relaxed">
        {diffLines.map((line, index) => (
          <span
            key={`${tool.id}-diff-${index}`}
            className={cn(
              "block whitespace-pre-wrap px-2.5 py-px",
              line.type === "add" && "bg-success/10 text-success",
              line.type === "remove" && "bg-destructive/10 text-destructive",
              line.type === "context" && "text-muted-foreground"
            )}
          >
            {line.type === "add" ? "+" : line.type === "remove" ? "-" : " "} {line.text}
          </span>
        ))}
      </pre>
    </DetailCard>
  )
}
