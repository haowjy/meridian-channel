import type { ComponentType, ReactNode } from "react"

import { CaretDown, CaretRight } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type ItemLineProps = {
  icon: ComponentType<{ className?: string }>
  label: string
  labelClassName?: string
  expanded?: boolean
  onToggle?: () => void
  children?: ReactNode
  detail?: ReactNode
  className?: string
}

export function ItemLine({
  icon: Icon,
  label,
  labelClassName,
  expanded,
  onToggle,
  children,
  detail,
  className,
}: ItemLineProps) {
  const isExpandable = typeof expanded === "boolean" && typeof onToggle === "function"

  return (
    <div
      className={cn(
        "grid grid-cols-[1.375rem_1fr_auto] px-3",
        // Hover highlight on expandable items (tools, thinking)
        isExpandable && "rounded-sm transition-colors hover:bg-foreground/[0.04]",
        className
      )}
    >
      {isExpandable ? (
        <Button
          variant="ghost"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`}
          className="col-span-2 flex min-h-10 min-w-0 items-center justify-start gap-0 rounded-none px-0 py-2 text-sm font-normal has-[>svg]:px-0 hover:bg-transparent hover:opacity-70"
        >
          <span className="flex w-[1.375rem] shrink-0 items-center justify-center">
            <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
          </span>
          <span className={cn("truncate text-foreground", labelClassName)}>{label}</span>
        </Button>
      ) : (
        <div className="col-span-2 flex min-h-10 min-w-0 items-center gap-0 py-2">
          <span className="flex w-[1.375rem] shrink-0 items-center justify-center">
            <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
          </span>
          <span className={cn("truncate text-foreground", labelClassName)}>{label}</span>
        </div>
      )}

      <span className="flex min-h-10 items-center gap-2 py-2">
        {children}
        {isExpandable ? (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            aria-hidden="true"
            tabIndex={-1}
            className="size-5 rounded-none text-muted-foreground hover:text-foreground"
          >
            {expanded ? (
              <CaretDown className="size-3.5" />
            ) : (
              <CaretRight className="size-3.5" />
            )}
          </Button>
        ) : null}
      </span>

      {detail ? <div className="col-span-3 pb-2 pl-[11px]">{detail}</div> : null}
    </div>
  )
}
