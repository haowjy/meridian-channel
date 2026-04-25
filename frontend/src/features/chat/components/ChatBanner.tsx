import { Lightning, XCircle } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"

// ---------------------------------------------------------------------------
// Chat banner — status indicator
// ---------------------------------------------------------------------------

export interface ChatBannerProps {
  chatState: string
  isActive: boolean
  isStreaming: boolean
  onCancel: () => void
}

export function ChatBanner({ chatState, isActive, isStreaming, onCancel }: ChatBannerProps) {
  if (chatState === "closed") {
    return (
      <div className="flex items-center gap-2 border-b border-border/40 bg-muted/20 px-4 py-1.5 text-xs text-muted-foreground">
        <XCircle weight="fill" className="size-3.5 text-zinc-400" />
        Chat closed
      </div>
    )
  }

  if (isActive || isStreaming) {
    return (
      <div className="flex items-center justify-between border-b border-emerald-500/20 bg-emerald-500/5 px-4 py-1.5">
        <div className="flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-400">
          <Lightning weight="fill" className="size-3.5" />
          {isStreaming ? "Streaming response..." : "Processing..."}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onCancel}
          className="h-6 px-2 text-[10px] text-destructive hover:text-destructive"
        >
          Cancel
        </Button>
      </div>
    )
  }

  return null
}
