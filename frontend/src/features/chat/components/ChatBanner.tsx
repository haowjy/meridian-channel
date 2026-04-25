import { CheckCircle, EyeClosed, Lightning } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"

// ---------------------------------------------------------------------------
// Chat UI state — drives banner appearance
// ---------------------------------------------------------------------------

export type ChatUIState = "zero" | "loading" | "active" | "idle" | "readonly" | "finished"

// ---------------------------------------------------------------------------
// Chat banner — status indicator
// ---------------------------------------------------------------------------

export interface ChatBannerProps {
  uiState: ChatUIState
  isStreaming: boolean
  onCancel: () => void
}

export function ChatBanner({ uiState, isStreaming, onCancel }: ChatBannerProps) {
  if (uiState === "readonly") {
    return (
      <div className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/5 px-4 py-1.5 text-xs text-amber-700 dark:text-amber-400">
        <EyeClosed weight="fill" className="size-3.5" />
        <span className="font-medium">Read-only</span>
        <span className="text-amber-600/70 dark:text-amber-400/70">&mdash; primary session elsewhere</span>
      </div>
    )
  }

  if (uiState === "finished") {
    return (
      <div className="flex items-center gap-2 border-b border-border/40 bg-muted/20 px-4 py-1.5 text-xs text-muted-foreground">
        <CheckCircle weight="fill" className="size-3.5 text-zinc-400 dark:text-zinc-500" />
        <span>Chat finished</span>
      </div>
    )
  }

  if (uiState === "active" || isStreaming) {
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
