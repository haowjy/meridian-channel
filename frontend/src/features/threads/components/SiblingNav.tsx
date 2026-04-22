import { CaretLeft, CaretRight } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type SiblingNavProps = {
  current: number
  total: number
  onPrevious?: () => void
  onNext?: () => void
  className?: string
}

export function SiblingNav({ current, total, onPrevious, onNext, className }: SiblingNavProps) {
  const safeTotal = Math.max(total, 1)
  const clampedCurrent = Math.min(Math.max(current, 0), safeTotal - 1)
  const canGoPrevious = clampedCurrent > 0
  const canGoNext = clampedCurrent < safeTotal - 1

  return (
    <div className={cn("mb-1 flex items-center gap-1 text-xs text-muted-foreground", className)}>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6 rounded-full"
        aria-label="Previous sibling turn"
        onClick={onPrevious}
        disabled={!canGoPrevious || !onPrevious}
      >
        <CaretLeft className="size-3.5" aria-hidden="true" />
      </Button>
      <span className="min-w-10 text-center tabular-nums">
        {clampedCurrent + 1}/{safeTotal}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6 rounded-full"
        aria-label="Next sibling turn"
        onClick={onNext}
        disabled={!canGoNext || !onNext}
      >
        <CaretRight className="size-3.5" aria-hidden="true" />
      </Button>
    </div>
  )
}
