import { Brain } from "@phosphor-icons/react"

import { ItemLine } from "../ItemLine"
import type { ThinkingItem } from "../types"

type ThinkingRowProps = {
  item: ThinkingItem
  expanded: boolean
  onToggle: () => void
}

export function ThinkingRow({ item, expanded, onToggle }: ThinkingRowProps) {
  return (
    <ItemLine
      icon={Brain}
      label="Thinking"
      labelClassName="italic text-muted-foreground"
      expanded={expanded}
      onToggle={onToggle}
      detail={
        expanded ? (
          <div className="rounded-md border-l-2 border-l-muted-foreground/30 pl-2.5">
            <p className="whitespace-pre-line text-sm italic text-muted-foreground">
              {item.text}
            </p>
          </div>
        ) : undefined
      }
    />
  )
}
