import { Skeleton } from "@/components/ui/skeleton"

export function StreamingIndicator() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
      <div className="flex items-center gap-1" aria-hidden="true">
        <Skeleton className="size-2 rounded-full" />
        <Skeleton className="size-2 rounded-full [animation-delay:120ms]" />
        <Skeleton className="size-2 rounded-full [animation-delay:240ms]" />
      </div>
      <span>Agent is working...</span>
    </div>
  )
}
