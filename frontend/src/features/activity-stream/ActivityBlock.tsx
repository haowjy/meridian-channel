import { Fragment, useCallback, useMemo, useState } from "react"

import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { ActivityBlockHeader } from "./ActivityBlockHeader"
import { ActivityNestingProvider } from "./activity-context"
import { ContentRow } from "./items/ContentRow"
import { ThinkingRow } from "./items/ThinkingRow"
import { ToolRow } from "./items/ToolRow"
import type { ActivityBlockData, ActivityItem, ToolItem } from "./types"

type ActivityBlockProps = {
  activity: ActivityBlockData
  isWaitingSubagents?: boolean
  expanded?: boolean
  defaultExpanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
  defaultShowAllTools?: boolean
  defaultExpandedToolIds?: string[]
  depth?: number
  className?: string
}

function isToolItem(item: ActivityItem): item is ToolItem {
  return item.kind === "tool"
}

export function ActivityBlock({
  activity,
  isWaitingSubagents = false,
  expanded,
  defaultExpanded = false,
  onExpandedChange,
  defaultShowAllTools = false,
  defaultExpandedToolIds = [],
  depth = 0,
  className,
}: ActivityBlockProps) {
  const [internalExpanded, setInternalExpanded] = useState(defaultExpanded)
  const [showAllTools, setShowAllTools] = useState(defaultShowAllTools)
  const [expandedTools, setExpandedTools] = useState(() => new Set(defaultExpandedToolIds))
  const isControlled = typeof expanded === "boolean"
  const isExpanded = isControlled ? expanded : internalExpanded
  const isStreaming = Boolean(activity.isStreaming)

  const setExpanded = (nextExpanded: boolean) => {
    if (!isControlled) {
      setInternalExpanded(nextExpanded)
    }

    onExpandedChange?.(nextExpanded)
  }

  const toggleExpanded = (id: string) => {
    setExpandedTools((current) => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Last content item renders below the block as the response.
  // Earlier content stays inside (narration between tools).
  const { blockItems, responseText } = useMemo(() => {
    let lastContentItem: ActivityItem | undefined
    for (let i = activity.items.length - 1; i >= 0; i--) {
      if (activity.items[i].kind === "content") {
        lastContentItem = activity.items[i]
        break
      }
    }
    return {
      blockItems: lastContentItem
        ? activity.items.filter((i) => i !== lastContentItem)
        : activity.items,
      responseText: lastContentItem?.kind === "content" ? lastContentItem.text : undefined,
    }
  }, [activity.items])

  const tools = useMemo(
    () => blockItems.filter((item): item is ToolItem => isToolItem(item)),
    [blockItems]
  )

  const hiddenToolCount = Math.max(tools.length - 3, 0)
  const visibleItems = useMemo(() => {
    if (showAllTools || hiddenToolCount === 0) {
      return blockItems
    }

    const firstVisibleTool = tools[hiddenToolCount]
    if (!firstVisibleTool) {
      return blockItems
    }

    const startIndex = blockItems.findIndex(
      (item) => item.kind === "tool" && item.id === firstVisibleTool.id
    )

    if (startIndex < 0) {
      return blockItems
    }

    return blockItems.slice(startIndex)
  }, [blockItems, hiddenToolCount, showAllTools, tools])

  const renderNestedActivity = useCallback(
    (nested: ActivityBlockData, nestedDepth: number) => (
      <ActivityBlock
        activity={nested}
        depth={nestedDepth}
        defaultExpanded={nestedDepth <= 1}
        className="mt-2"
      />
    ),
    []
  )

  // If there are no tools/thinking (only content), just render the response text
  const hasActivity = blockItems.length > 0

  return (
    <ActivityNestingProvider depth={depth} renderNestedActivity={renderNestedActivity}>
      <div className={cn("min-w-0 space-y-2", depth > 0 ? "ml-2 pl-1" : undefined, className)}>
        {hasActivity ? (
          <Collapsible open={isExpanded} onOpenChange={setExpanded}>
            <Card
              variant={depth > 0 ? "outline" : "muted"}
              className="gap-0 overflow-hidden rounded-lg border-border/70 bg-card/85 py-0"
            >
              <ActivityBlockHeader
                items={blockItems}
                isStreaming={isStreaming}
                isWaitingSubagents={isWaitingSubagents}
                expanded={isExpanded}
              />

              <CollapsibleContent>
                {hiddenToolCount > 0 ? (
                  <button
                    type="button"
                    onClick={() => setShowAllTools(!showAllTools)}
                    className="relative z-10 flex h-0 w-full cursor-pointer items-center justify-center"
                  >
                    <span className="absolute inset-x-4 top-1/2 h-px bg-border/70" />
                    <span className="relative rounded-full border border-border/70 bg-card px-2.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-border hover:text-foreground">
                      {showAllTools
                        ? "Collapse"
                        : `${hiddenToolCount} earlier ${hiddenToolCount === 1 ? "tool" : "tools"}...`}
                    </span>
                  </button>
                ) : null}

                <div>
                  {visibleItems.length === 0 ? (
                    <p className="px-3 py-2 text-sm text-muted-foreground">No activity yet.</p>
                  ) : (
                    visibleItems.map((item, index) => {
                      const row =
                        item.kind === "content" ? (
                          <ContentRow item={item} />
                        ) : item.kind === "thinking" ? (
                          <ThinkingRow
                            item={item}
                            expanded={expandedTools.has(item.id)}
                            onToggle={() => toggleExpanded(item.id)}
                          />
                        ) : (
                          <ToolRow
                            tool={item}
                            expanded={expandedTools.has(item.id)}
                            onToggle={() => toggleExpanded(item.id)}
                          />
                        )

                      return (
                        <Fragment key={item.id}>
                          {index > 0 && <div className="mx-4 h-px bg-border/30" />}
                          {row}
                        </Fragment>
                      )
                    })
                  )}
                </div>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        ) : null}

        {(responseText || (isStreaming && activity.pendingText)) ? (
          <p className="font-editor break-words text-base leading-relaxed text-foreground">
            {responseText || activity.pendingText}
          </p>
        ) : null}
      </div>
    </ActivityNestingProvider>
  )
}
