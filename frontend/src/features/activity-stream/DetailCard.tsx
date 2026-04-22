import type { ReactNode } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type DetailCardProps = {
  /** Accent left border (e.g., for agent details) */
  accent?: boolean
  children: ReactNode
  className?: string
}

/**
 * Shared wrapper for all tool detail content.
 * Subtle background distinguishes detail from the parent header row.
 */
export function DetailCard({ accent, children, className }: DetailCardProps) {
  return (
    <Card
      variant="outline"
      className={cn(
        "gap-0 rounded-md border-border/70 bg-card/90 py-0",
        accent && "border-l-2 border-l-accent-fill",
        className
      )}
    >
      <CardContent className="p-2">{children}</CardContent>
    </Card>
  )
}
