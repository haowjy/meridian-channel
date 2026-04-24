/**
 * ChatThreadView — full chat conversation view.
 *
 * Renders the conversation history for a selected chat, with:
 * - History loaded from getChatHistory on mount
 * - Live streaming via WS when the chat has an active spawn
 * - Composer at the bottom for sending follow-up messages
 * - Handling of chat lifecycle (idle → active → idle/closed)
 *
 * This is the main content area when a chat is selected and no
 * spawn columns are explicitly open.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  Lightning,
  Spinner,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { SpawnActivityView } from "@/features/threads/components/SpawnActivityView"
import type { StreamController } from "@/features/threads/transport-types"
import { useThreadStreaming } from "@/hooks/use-thread-streaming"

import { useChat } from "./ChatContext"
import {
  createChat,
  promptChat,
  cancelChat,
  getChat,
  ApiError,
  type ChatDetailResponse,
} from "@/features/sessions/lib/api"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ChatThreadViewProps {
  chatId: string
  className?: string
}

export function ChatThreadView({ chatId, className }: ChatThreadViewProps) {
  const { selectedChat, setChatState, setActiveSpawnId, selectChat } = useChat()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatDetail, setChatDetail] = useState<ChatDetailResponse | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [composerValue, setComposerValue] = useState("")

  const bottomRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const activeSpawnId = selectedChat?.activeSpawnId ?? chatDetail?.active_p_id ?? null

  // Stream the active spawn when one exists
  const { state: streamState, channel } =
    useThreadStreaming(activeSpawnId)

  const isStreaming = Boolean(streamState.isStreaming)
  const chatState = selectedChat?.chatState ?? chatDetail?.state ?? 'idle'
  const isActive = chatState === 'active' || chatState === 'draining'

  // Load chat detail on mount
  useEffect(() => {
    if (chatId === "__new__") return

    let cancelled = false
    getChat(chatId)
      .then((detail) => {
        if (cancelled) return
        setChatDetail(detail)
        if (detail.active_p_id) {
          setActiveSpawnId(detail.active_p_id)
        }
        setChatState(detail.state)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
      })

    return () => {
      cancelled = true
    }
  }, [chatId, setActiveSpawnId, setChatState])

  // Auto-scroll on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages.length, streamState.items.length, streamState.pendingText])

  // Resize textarea
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [])

  useEffect(() => {
    resizeTextarea()
  }, [resizeTextarea, composerValue])

  // --- Send logic ---

  const handleSend = useCallback(async () => {
    const text = composerValue.trim()
    if (!text) return

    setError(null)

    // Append user message to local state immediately
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])
    setComposerValue("")

    if (chatId === "__new__") {
      // Create a new chat
      setIsCreating(true)
      try {
        const detail = await createChat(text)
        setChatDetail(detail)
        // Update context with real chat ID
        selectChat(detail.chat_id, detail.state, detail.active_p_id)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setIsCreating(false)
      }
    } else {
      // Send follow-up to existing chat
      setIsSending(true)
      try {
        const detail = await promptChat(chatId, text)
        setChatDetail(detail)
        if (detail.active_p_id) {
          setActiveSpawnId(detail.active_p_id)
        }
        setChatState(detail.state)
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setError("Chat is busy — waiting for the current response to complete.")
        } else {
          setError(err instanceof Error ? err.message : String(err))
        }
      } finally {
        setIsSending(false)
      }
    }
  }, [composerValue, chatId, selectChat, setActiveSpawnId, setChatState])

  // Stream controller for the active spawn
  const controller = useMemo<StreamController>(
    () => ({
      sendMessage: (text) => channel.current?.sendMessage(text) ?? false,
      interrupt: () => channel.current?.interrupt() ?? false,
      cancel: () => {
        channel.current?.cancel()
      },
    }),
    [channel],
  )

  const handleCancel = useCallback(async () => {
    if (chatId === "__new__") return
    try {
      await cancelChat(chatId)
    } catch {
      // Cancellation is best-effort
    }
  }, [chatId])

  const composerDisabled = isCreating || isSending

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col",
        className,
      )}
    >
      {/* Chat header banner */}
      <ChatBanner
        chatState={chatState}
        isActive={isActive}
        isStreaming={isStreaming}
        onCancel={handleCancel}
      />

      {/* Thread area */}
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
          {/* Rendered messages */}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Live spawn activity */}
          {activeSpawnId && (streamState.items.length > 0 || streamState.pendingText) && (
            <div className="rounded-lg border border-border/50">
              <SpawnActivityView activity={streamState} />
            </div>
          )}

          {/* Loading indicator when creating/sending */}
          {(isCreating || isSending) && (
            <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
              <Spinner className="size-3.5 animate-spin" />
              <span>{isCreating ? "Starting chat..." : "Sending..."}</span>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-destructive/5 px-3 py-2 text-xs text-destructive">
              <WarningCircle className="mt-0.5 size-3.5 shrink-0" />
              <div>
                <p className="font-medium">Error</p>
                <p className="mt-0.5 text-muted-foreground">{error}</p>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Composer */}
      <div className="border-t border-border bg-background px-4 py-3">
        <div className="mx-auto max-w-3xl">
          <div className="rounded-lg border border-border bg-card px-3 py-3">
            <Textarea
              ref={textareaRef}
              value={composerValue}
              onChange={(e) => setComposerValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  void handleSend()
                }
              }}
              disabled={composerDisabled}
              placeholder={
                chatId === "__new__"
                  ? "Type your first message..."
                  : isActive
                    ? "Type a follow-up..."
                    : "Resume the conversation..."
              }
              className="max-h-[180px] min-h-12 resize-none font-editor"
            />

            <div className="mt-2 flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground/60">
                Enter to send &middot; Shift+Enter for newline
              </span>
              <div className="flex items-center gap-2">
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
                        disabled={composerDisabled || !composerValue.trim()}
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
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chat banner
// ---------------------------------------------------------------------------

interface ChatBannerProps {
  chatState: string
  isActive: boolean
  isStreaming: boolean
  onCancel: () => void
}

function ChatBanner({ chatState, isActive, isStreaming, onCancel }: ChatBannerProps) {
  if (chatState === 'closed') {
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

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "max-w-[80%] rounded-2xl rounded-br-md px-4 py-2.5",
            "bg-accent text-accent-foreground",
            "text-sm leading-relaxed",
          )}
        >
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div
        className={cn(
          "max-w-[80%] rounded-2xl rounded-bl-md px-4 py-2.5",
          "bg-muted text-foreground",
          "text-sm leading-relaxed",
        )}
      >
        {message.content}
      </div>
    </div>
  )
}
