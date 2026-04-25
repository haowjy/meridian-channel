/**
 * useChatConversation — unified hook for chat conversation state.
 *
 * Wires the pure chat state machine (chat-conversation-machine.ts) to
 * the effect runner (chat-conversation-effects.ts), producing the same
 * return contract that ChatThreadView consumes.
 *
 * Architecture:
 * 1. useReducer holds the ChatMachineContext
 * 2. A wrapper reducer captures emitted commands in a ref
 * 3. A post-dispatch effect flushes captured commands to the effect runner
 * 4. The effect runner executes I/O and dispatches response events back
 *
 * This replaces the original ad-hoc useEffect/useState approach with an
 * explicit phase machine and command model.
 */

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react"

import type { WsState } from "@/lib/ws"
import type { StreamController } from "../transport-types"
import type { ConversationEntry } from "../conversation-types"
import type { ActivityBlockData } from "@/features/activity-stream/types"
import type {
  ChatState as ApiChatState,
  ChatDetailResponse,
  CreateChatOptions,
} from "@/lib/api"

import {
  chatMachineReducer,
  createInitialMachineContext,
  deriveChatState,
} from "./chat-conversation-machine"
import type {
  ChatCommand,
  ChatEvent,
  ChatMachineContext,
  TransitionResult,
} from "./chat-conversation-types"
import { useEffectRunner } from "./chat-conversation-effects"

// ---------------------------------------------------------------------------
// Types (public contract — unchanged from the original hook)
// ---------------------------------------------------------------------------

export interface UseChatConversationOptions {
  chatId: string
  initialPrompt?: string | null
  createChatOptions?: CreateChatOptions
  onChatCreated?: (detail: ChatDetailResponse) => void
}

export interface UseChatConversationReturn {
  entries: ConversationEntry[]
  currentActivity: ActivityBlockData | null
  isStreaming: boolean
  isLoading: boolean
  isCreating: boolean
  isSending: boolean
  connectionState: WsState
  controller: StreamController
  chatState: ApiChatState | null
  chatDetail: ChatDetailResponse | null
  activeSpawnId: string | null
  error: string | null
  sendMessage: (text: string) => Promise<void>
  cancel: () => Promise<void>
}

// ---------------------------------------------------------------------------
// Wrapper reducer — captures commands in a ref for the effect runner
// ---------------------------------------------------------------------------

/**
 * We can't execute side effects inside a reducer, so we wrap the
 * machine reducer to stash emitted commands in a mutable ref. The
 * hook reads and flushes this ref after each dispatch via useEffect.
 */
type CommandSink = { current: ChatCommand[] }

function createWrappedReducer(commandSink: CommandSink) {
  return function wrappedReducer(
    ctx: ChatMachineContext,
    event: ChatEvent,
  ): ChatMachineContext {
    const result: TransitionResult = chatMachineReducer(ctx, event)
    // Append commands — multiple dispatches in a single render batch
    // accumulate into the same array, flushed once in useEffect.
    if (result.commands.length > 0) {
      commandSink.current = [...commandSink.current, ...result.commands]
    }
    return result.context
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChatConversation({
  chatId,
  initialPrompt,
  createChatOptions,
  onChatCreated,
}: UseChatConversationOptions): UseChatConversationReturn {
  // ---- Command capture ----
  // Stable ref survives re-renders; the wrapped reducer appends here.
  const commandSinkRef = useRef<ChatCommand[]>([])
  const wrappedReducer = useMemo(
    () => createWrappedReducer(commandSinkRef),
    [],
  )

  const [ctx, rawDispatch] = useReducer(wrappedReducer, undefined, createInitialMachineContext)

  // ---- Stable callback refs ----
  const onChatCreatedRef = useRef(onChatCreated)
  onChatCreatedRef.current = onChatCreated

  // ---- Effect runner ----
  const effectRunner = useEffectRunner(rawDispatch, {
    createChatOptions,
    callbacks: {
      onChatCreated: (detail) => onChatCreatedRef.current?.(detail),
    },
  })

  // ---- Flush commands after each render that produced them ----
  // useEffect runs after React commits the state update, so ctx is
  // consistent with the commands being flushed.
  useEffect(() => {
    const commands = commandSinkRef.current
    if (commands.length === 0) return
    commandSinkRef.current = []
    effectRunner.executeCommands(commands)
  })

  // -----------------------------------------------------------------------
  // Chat selection — translate external chatId into machine events
  // -----------------------------------------------------------------------

  const prevChatIdRef = useRef<string | null>(null)
  const didMount = useRef(false)

  useEffect(() => {
    if (!didMount.current) {
      // First mount — fire the initial selection event
      didMount.current = true
      prevChatIdRef.current = chatId

      if (chatId === "__new__") {
        rawDispatch({ type: "SELECT_ZERO" })
      } else {
        rawDispatch({ type: "SELECT_CHAT", chatId })
      }
      return
    }

    // Subsequent chatId changes
    if (prevChatIdRef.current === chatId) return
    const wasNew = prevChatIdRef.current === "__new__"
    prevChatIdRef.current = chatId

    // Transition from __new__ → real ID means the create succeeded and
    // the machine already has the right state. Don't re-select.
    if (wasNew && chatId !== "__new__") {
      return
    }

    if (chatId === "__new__") {
      rawDispatch({ type: "SELECT_ZERO" })
    } else {
      rawDispatch({ type: "SELECT_CHAT", chatId })
    }
  }, [chatId, rawDispatch])

  // -----------------------------------------------------------------------
  // Auto-send initial prompt for new chats
  // -----------------------------------------------------------------------

  const didAutoSend = useRef(false)
  const prevInitialPrompt = useRef(initialPrompt)

  useEffect(() => {
    if (!initialPrompt) return
    if (chatId !== "__new__") return
    // Only auto-send once per initialPrompt value
    if (didAutoSend.current && prevInitialPrompt.current === initialPrompt) return

    didAutoSend.current = true
    prevInitialPrompt.current = initialPrompt

    rawDispatch({
      type: "SEND_MESSAGE",
      text: initialPrompt,
      id: `user-${Date.now()}`,
      sentAt: new Date(),
    })
  }, [initialPrompt, chatId, rawDispatch])

  // Reset auto-send flag when chatId changes
  useEffect(() => {
    didAutoSend.current = false
  }, [chatId])

  // -----------------------------------------------------------------------
  // Cleanup on unmount
  // -----------------------------------------------------------------------

  useEffect(() => {
    return () => {
      effectRunner.destroy()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // -----------------------------------------------------------------------
  // User actions
  // -----------------------------------------------------------------------

  const sendMessage = useCallback(
    async (text: string) => {
      rawDispatch({
        type: "SEND_MESSAGE",
        text,
        id: `user-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        sentAt: new Date(),
      })
    },
    [rawDispatch],
  )

  const cancel = useCallback(async () => {
    rawDispatch({ type: "CANCEL" })
  }, [rawDispatch])

  // -----------------------------------------------------------------------
  // Stream controller
  // -----------------------------------------------------------------------

  const controller = useMemo<StreamController>(
    () => ({
      sendMessage: (msg) => effectRunner.getChannel()?.sendMessage(msg) ?? false,
      interrupt: () => effectRunner.getChannel()?.interrupt() ?? false,
      cancel: () => {
        effectRunner.getChannel()?.cancel()
      },
    }),
    [effectRunner],
  )

  // -----------------------------------------------------------------------
  // Derived state
  // -----------------------------------------------------------------------

  const derived = deriveChatState(ctx)

  // Map machine transportState to the WsState the view expects
  const connectionState: WsState = ctx.transportState

  return {
    entries: ctx.entries,
    currentActivity: derived.currentActivity,
    isStreaming: derived.isStreaming,
    isLoading: derived.isLoading,
    isCreating: derived.isCreating,
    isSending: derived.isSending,
    connectionState,
    controller,
    chatState: ctx.chatState,
    chatDetail: ctx.chatDetail,
    activeSpawnId: ctx.activeSpawnId,
    error: ctx.error,
    sendMessage,
    cancel,
  }
}
