import { Check, CircleNotch, X } from "@phosphor-icons/react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import { ItemLine } from "../ItemLine"
import { ToolDetail } from "../ToolDetail"
import {
  getToolCategory,
  getToolIcon,
  getToolLineTitle,
  getToolStatusLabel,
  getToolStatusVariant,
} from "../tool-utils"
import type { ToolItem } from "../types"

type ToolRowProps = {
  tool: ToolItem
  expanded: boolean
  onToggle: () => void
  onViewFile?: () => void
  className?: string
}

function ToolStatusGlyph({ status }: Pick<ToolItem, "status">) {
  if (status === "done") {
    return <Check className="size-3" aria-hidden="true" />
  }

  if (status === "error") {
    return <X className="size-3" aria-hidden="true" />
  }

  return (
    <CircleNotch
      className={cn("size-3", (status === "executing" || status === "streaming-args") ? "animate-spin" : undefined)}
      aria-hidden="true"
    />
  )
}

export function ToolRow({ tool, expanded, onToggle, onViewFile, className }: ToolRowProps) {
  const category = getToolCategory(tool.toolName ?? "")
  const Icon = getToolIcon(category)
  const title = getToolLineTitle(tool, category)
  const statusText = getToolStatusLabel(tool.status)
  const statusVariant = getToolStatusVariant(tool.status)
  const isRead = category === "read"
  const hasDetail = !isRead

  return (
    <ItemLine
      icon={Icon}
      label={title}
      expanded={hasDetail ? expanded : undefined}
      onToggle={hasDetail ? onToggle : isRead ? onViewFile : undefined}
      className={className}
      detail={hasDetail && expanded ? <ToolDetail tool={tool} /> : undefined}
    >
      <Badge variant={statusVariant} className="h-5 px-2 text-[11px] font-medium">
        <ToolStatusGlyph status={tool.status} />
        {statusText}
      </Badge>
    </ItemLine>
  )
}
