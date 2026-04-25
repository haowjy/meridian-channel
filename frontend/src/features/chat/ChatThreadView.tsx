import { useCallback, useMemo } from "react"
import {
  Spinner,
  WarningCircle,
} from "@phosphor-icons/react"

import { cn } from "@/lib/utils"
import { ConversationView } from "@/features/threads/components/ConversationView"

import { useChat } from "./ChatContext"
import { ChatBanner } from "./components/ChatBanner"
import { Composer } from "./components/Composer"
import { useChatConversation } from "./hooks/use-chat-conversation"

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ChatThreadViewProps {
  chatId: string
  className?: string
}

export function ChatThreadView({ chatId, className }: ChatThreadViewProps) {
  const { selectedChat, setChatState, setActiveSpawnId, selectChat } = useChat()

  const activeSpawnId = selectedChat?.active_p_id ?? null
  const initialPrompt = selectedChat?.initialPrompt ?? null

  const {
    entries,
    currentActivity,
    isStreaming,
    isLoading,
    isCreating,
    isSending,
    connectionState,
    controller,
    chatState: hookChatState,
    chatDetail,
    error,
    sendMessage,
    cancel,
  } = useChatConversation({
    chatId,
    activeSpawnId,
    initialPrompt,
    onChatCreated: (detail) => {
      selectChat(detail, { initialPrompt: null })
      setActiveSpawnId(detail.active_p_id)
    },
    onSpawnStarted: (spawnId) => {
      setActiveSpawnId(spawnId)
    },
    onChatStateChange: (state) => {
      setChatState(state)
    },
  })

  const chatState = selectedChat?.state ?? hookChatState ?? "idle"
  const isActive = chatState === "active" || chatState === "draining"
  const composerDisabled = isCreating || isSending
  const threadTitle = selectedChat?.title ?? "New chat"
  const threadModel = chatDetail?.model ?? selectedChat?.model ?? null
  const threadHarness = useMemo(() => {
    const activeSpawnId = selectedChat?.active_p_id ?? null
    if (!activeSpawnId) return null
    return chatDetail?.spawns.find((spawn) => spawn.spawn_id === activeSpawnId)?.harness ?? null
  }, [chatDetail, selectedChat?.active_p_id])

  const handleCancel = useCallback(async () => {
    await cancel()
  }, [cancel])

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col",
        className,
      )}
    >
      <div className="border-b border-border bg-background/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-foreground">
              {threadTitle}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono uppercase tracking-wide">
                model: {threadModel ?? "unknown"}
              </span>
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono uppercase tracking-wide">
                harness: {threadHarness ?? "unknown"}
              </span>
            </div>
          </div>
          <div className="shrink-0 rounded-full border border-border/70 bg-muted/40 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Chat
          </div>
        </div>
      </div>

      {/* Chat header banner */}
      <ChatBanner
        chatState={chatState}
        isActive={isActive}
        isStreaming={isStreaming}
        onCancel={handleCancel}
      />

      {/* Conversation area — unified entries + live streaming */}
      <ConversationView
        entries={entries}
        currentActivity={currentActivity}
        isConnecting={connectionState === "connecting" || isLoading}
      />

      {/* Loading indicator when creating/sending */}
      {(isCreating || isSending) && (
        <div className="flex items-center gap-2 border-t border-border/30 px-5 py-2 text-xs text-muted-foreground">
          <Spinner className="size-3.5 animate-spin" />
          <span>{isCreating ? "Starting chat..." : "Sending..."}</span>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="flex items-start gap-2 border-t border-destructive/10 bg-destructive/5 px-5 py-2 text-xs text-destructive">
          <WarningCircle className="mt-0.5 size-3.5 shrink-0" />
          <div>
            <p className="font-medium">Error</p>
            <p className="mt-0.5 text-muted-foreground">{error}</p>
          </div>
        </div>
      )}

      {/* Composer — always visible (EARS-CHAT-040) */}
      <Composer
        onSend={sendMessage}
        disabled={composerDisabled}
        isStreaming={isStreaming}
        placeholder={
          chatId === "__new__"
            ? "Type your first message..."
            : isActive
              ? "Type a follow-up..."
              : "Resume the conversation..."
        }
        controller={controller}
      />
    </div>
  )
}
