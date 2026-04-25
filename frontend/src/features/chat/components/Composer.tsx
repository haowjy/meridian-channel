import { useCallback, useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { StreamController } from "@/features/threads/transport-types"

// ---------------------------------------------------------------------------
// Composer — message input with send/interrupt controls
// ---------------------------------------------------------------------------

export interface ComposerProps {
  onSend: (text: string) => void | Promise<void>
  disabled: boolean
  isStreaming: boolean
  placeholder: string
  controller: StreamController
}

export function Composer({
  onSend,
  disabled,
  isStreaming,
  placeholder,
  controller,
}: ComposerProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Auto-resize textarea
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [])

  useEffect(() => {
    resizeTextarea()
  }, [resizeTextarea, value])

  const handleSend = useCallback(async () => {
    const text = value.trim()
    if (!text) return
    setValue("")
    await onSend(text)
  }, [value, onSend])

  return (
    <div className="border-t border-border bg-background px-4 py-3">
      <div className="mx-auto max-w-3xl">
        <div className="rounded-lg border border-border bg-card px-3 py-3">
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                void handleSend()
              }
            }}
            disabled={disabled}
            placeholder={placeholder}
            className="max-h-[180px] min-h-12 resize-none font-editor"
          />

          <div className="mt-2 flex items-center justify-between">
            <span className="text-[10px] text-muted-foreground/60">
              Enter to send &middot; Shift+Enter for newline
            </span>
            <div className="flex items-center gap-2">
              {/* EARS-CHAT-042: Interrupt button during streaming */}
              {isStreaming && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => controller.interrupt()}
                >
                  Interrupt
                </Button>
              )}
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void handleSend()}
                      disabled={disabled || !value.trim()}
                    >
                      Send
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" sideOffset={6}>
                  Send message
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
