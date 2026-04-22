import { useState } from "react"
import { CaretRight } from "@phosphor-icons/react"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Skeleton } from "@/components/ui/skeleton"
import { ElapsedTime } from "@/components/atoms"
import { cn } from "@/lib/utils"

export interface WorkItemGroupHeaderProps {
  name: string
  spawnCount: number
  lastActivity?: Date
  defaultOpen?: boolean
  children: React.ReactNode
  className?: string
}

export function WorkItemGroupHeader({
  name,
  spawnCount,
  lastActivity,
  defaultOpen = true,
  children,
  className,
}: WorkItemGroupHeaderProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("w-full", className)}
    >
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex w-full items-center gap-2 px-3 py-2",
            "bg-muted/30 hover:bg-muted/50 transition-colors",
            "border-b border-border"
          )}
        >
          <CaretRight
            size={14}
            weight="bold"
            className={cn(
              "shrink-0 text-muted-foreground transition-transform",
              "duration-[var(--duration-default)]",
              isOpen && "rotate-90"
            )}
          />
          <span className="font-medium text-sm truncate flex-1 text-left">
            {name}
          </span>
          <Badge variant="secondary" className="font-mono text-xs">
            {spawnCount}
          </Badge>
          {lastActivity && (
            <ElapsedTime
              startedAt={lastActivity}
              format="relative"
              className="text-muted-foreground"
            />
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent
        className={cn(
          "overflow-hidden",
          "data-[state=open]:animate-in data-[state=closed]:animate-out",
          "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          "data-[state=closed]:slide-out-to-top-1 data-[state=open]:slide-in-from-top-1",
          "transition-all duration-[var(--duration-default)]"
        )}
      >
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}

// Skeleton variant for loading state
export function WorkItemGroupHeaderSkeleton({
  className,
}: {
  className?: string
}) {
  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/30 border-b border-border">
        <Skeleton className="h-3.5 w-3.5" />
        <Skeleton className="h-4 w-32 flex-1" />
        <Skeleton className="h-5 w-8 rounded-full" />
        <Skeleton className="h-3 w-14" />
      </div>
    </div>
  )
}
