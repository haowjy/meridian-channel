/**
 * Chat-only context.
 *
 * Tracks which chat is selected (navigation identity) and model picker state.
 * Lifecycle state (chatState, activeSpawnId, chatDetail) is owned by the
 * chat conversation machine — not duplicated here.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

import type { ChatProjection } from "@/lib/api"

export interface ChatSelection extends ChatProjection {
  initialPrompt: string | null
}

export interface ModelSelection {
  modelId: string
  harness: string
  displayName: string
}

export interface ChatContextValue {
  selectedChat: ChatSelection | null
  selectChat: (
    chat: ChatProjection,
    options?: { initialPrompt?: string | null },
  ) => void
  clearChat: () => void
  modelSelection: ModelSelection | null
  setModelSelection: (selection: ModelSelection | null) => void
}

export const ChatContext = createContext<ChatContextValue | null>(null)

interface ChatProviderProps {
  children: ReactNode
}

export function ChatProvider({ children }: ChatProviderProps) {
  const [selectedChat, setSelectedChat] = useState<ChatSelection | null>(null)
  const [modelSelection, setModelSelection] = useState<ModelSelection | null>(null)

  const selectChat = useCallback(
    (chat: ChatProjection, options?: { initialPrompt?: string | null }) => {
      setSelectedChat({
        ...chat,
        initialPrompt: options?.initialPrompt ?? null,
      })
    },
    [],
  )

  // modelSelection intentionally NOT cleared — persists across chat switches
  const clearChat = useCallback(() => {
    setSelectedChat(null)
  }, [])

  const value = useMemo<ChatContextValue>(
    () => ({
      selectedChat,
      selectChat,
      clearChat,
      modelSelection,
      setModelSelection,
    }),
    [selectedChat, selectChat, clearChat, modelSelection],
  )

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error("useChat must be used within a ChatProvider")
  }
  return ctx
}
