/**
 * Chat conversation state machine — type definitions.
 *
 * Defines the phase model, context shape, command vocabulary, and event
 * discriminated union that drive the chat lifecycle state machine.
 *
 * The machine is pure — no I/O. An effect runner (subphase 2.2) reads
 * the emitted commands and performs the actual API/WS work.
 */

import type { WsState } from "@/lib/ws"
import type {
  ChatDetailResponse,
  ChatState as ApiChatState,
  CreateChatOptions,
} from "@/lib/api"
import type { StreamEvent } from "@/features/activity-stream/streaming/events"
import type { StreamState } from "@/features/activity-stream/streaming/reducer"
import type { ActivityBlockData } from "@/features/activity-stream/types"
import type { ConversationEntry } from "../conversation-types"

// ═══════════════════════════════════════════════════════════════════
// Phase model
// ═══════════════════════════════════════════════════════════════════

/**
 * Lifecycle phases — each phase carries specific invariants about what
 * data is present, what transport is active, and what user actions are
 * allowed. See the spec's "State Invariants" table for the full contract.
 */
export type ChatPhase =
  | "zero"       // No selected chat; composer ready
  | "creating"   // First message sent; create API call in flight
  | "loading"    // Existing chat selected; detail + history bootstrap in flight
  | "connecting" // Chat exists; attaching to live spawn
  | "streaming"  // Live assistant turn in progress
  | "idle"       // Chat open; waiting for next user message
  | "readonly"   // Chat open; control commands blocked (external launch_mode)
  | "finished"   // Chat closed; no live spawn

export type AccessMode = "interactive" | "readonly"

// ═══════════════════════════════════════════════════════════════════
// Bootstrap tracking
// ═══════════════════════════════════════════════════════════════════

/**
 * Tracks the two independent REST calls (detail + history) that must
 * both complete before `loading` can resolve to its target phase.
 */
export interface BootstrapState {
  detailLoaded: boolean
  historyLoaded: boolean
  detailPayload: ChatDetailResponse | null
  historyPayload: ConversationEntry[] | null
}

// ═══════════════════════════════════════════════════════════════════
// Pending operation
// ═══════════════════════════════════════════════════════════════════

export type PendingOperation =
  | { kind: "create"; prompt: string; options?: CreateChatOptions }
  | { kind: "prompt"; chatId: string; text: string }
  | { kind: "cancel"; chatId: string }
  | { kind: "continue"; chatId: string; text: string }

// ═══════════════════════════════════════════════════════════════════
// Cache snapshot (Phase 5 placeholder — structure only)
// ═══════════════════════════════════════════════════════════════════

/**
 * Snapshot captured when a chat is evicted from view or switched away.
 * Used for instant restoration without a REST round-trip.
 */
export interface ChatCacheSnapshot {
  chatId: string
  chatDetail: ChatDetailResponse
  chatState: ApiChatState
  entries: ConversationEntry[]
  turnSeq: number
  activeSpawnId: string | null
  /** Whether the cached chat was in a terminal state (finished/readonly). */
  isTerminal: boolean
}

// ═══════════════════════════════════════════════════════════════════
// Machine context
// ═══════════════════════════════════════════════════════════════════

export interface ChatMachineContext {
  // ---- Identity ----
  chatId: string | null
  phase: ChatPhase

  // ---- Access mode ----
  accessMode: AccessMode

  // ---- Bootstrap data ----
  chatDetail: ChatDetailResponse | null
  chatState: ApiChatState | null
  activeSpawnId: string | null

  // ---- Conversation (inner reducer) ----
  entries: ConversationEntry[]
  current: StreamState | null
  turnSeq: number

  // ---- Transport ----
  transportState: WsState

  // ---- Generation guards (prevent stale callbacks) ----
  requestGeneration: number   // Increments on selection/bootstrap
  streamGeneration: number    // Increments on WS attach
  createGeneration: number    // Increments on create/continue attempt

  // ---- Bootstrap tracking ----
  bootstrap: BootstrapState

  // ---- Pending operation ----
  pendingOp: PendingOperation | null

  // ---- Error ----
  error: string | null

  // ---- Terminal tracking ----
  terminalSeen: boolean

  // ---- Cache snapshot (Phase 5) ----
  cacheSnapshot: ChatCacheSnapshot | null
}

// ═══════════════════════════════════════════════════════════════════
// Commands — emitted by the reducer, executed by the effect runner
// ═══════════════════════════════════════════════════════════════════

export type ChatCommand =
  | { type: "fetchDetail"; chatId: string; generation: number }
  | { type: "fetchHistory"; chatId: string; generation: number }
  | { type: "createChat"; prompt: string; options?: CreateChatOptions; generation: number }
  | { type: "promptChat"; chatId: string; text: string; generation: number }
  | { type: "continueChat"; chatId: string; text: string; generation: number }
  | { type: "cancelChat"; chatId: string; generation: number }
  | { type: "connectSpawn"; spawnId: string; replay: boolean; generation: number }
  | { type: "fetchReplay"; spawnId: string; generation: number }
  | { type: "disconnectSpawn"; generation: number }

// ═══════════════════════════════════════════════════════════════════
// Events — dispatched to the reducer
// ═══════════════════════════════════════════════════════════════════

export type ChatEvent =
  // ---- Selection ----
  | { type: "SELECT_ZERO" }
  | { type: "SELECT_CHAT"; chatId: string; cached?: ChatCacheSnapshot }

  // ---- Bootstrap responses ----
  | { type: "DETAIL_LOADED"; detail: ChatDetailResponse; generation: number }
  | { type: "DETAIL_FAILED"; error: string; generation: number }
  | { type: "HISTORY_LOADED"; entries: ConversationEntry[]; generation: number }
  | { type: "HISTORY_FAILED"; error: string; generation: number }

  // ---- API responses ----
  | { type: "CREATE_SUCCEEDED"; detail: ChatDetailResponse; generation: number }
  | { type: "CREATE_FAILED"; error: string; generation: number }
  | { type: "PROMPT_SUCCEEDED"; detail: ChatDetailResponse; generation: number }
  | { type: "PROMPT_FAILED"; error: string; generation: number }
  | { type: "CANCEL_SUCCEEDED"; generation: number }
  | { type: "CANCEL_FAILED"; error: string; generation: number }
  | { type: "CONTINUE_SUCCEEDED"; detail: ChatDetailResponse; generation: number }
  | { type: "CONTINUE_FAILED"; error: string; generation: number }

  // ---- WS lifecycle ----
  | { type: "WS_OPENED"; generation: number }
  | { type: "WS_CLOSED"; generation: number }

  // ---- Stream events (activity-stream reducer) ----
  | { type: "STREAM_EVENT"; event: StreamEvent; generation: number }

  // ---- Replay ----
  | { type: "REPLAY_SUCCEEDED"; entries: ConversationEntry[]; cursor: number; generation: number }
  | { type: "REPLAY_FAILED"; error: string; generation: number }

  // ---- User actions ----
  | { type: "SEND_MESSAGE"; text: string; id: string; sentAt: Date }
  | { type: "CANCEL" }
  | { type: "UNMOUNT" }

// ═══════════════════════════════════════════════════════════════════
// Transition result
// ═══════════════════════════════════════════════════════════════════

/**
 * Every reducer invocation returns the next context AND zero or more
 * commands for the effect runner to execute.
 */
export interface TransitionResult {
  context: ChatMachineContext
  commands: ChatCommand[]
}

// ═══════════════════════════════════════════════════════════════════
// Derived state — convenience getters for the render tree
// ═══════════════════════════════════════════════════════════════════

/**
 * Derived booleans the component tree consumes. Computed from context,
 * never stored. Keeps the render layer from inspecting phases directly.
 */
export interface ChatDerivedState {
  /** True when the assistant is actively producing tokens. */
  isStreaming: boolean
  /** True during initial REST bootstrap. */
  isLoading: boolean
  /** True while the create API call is in flight. */
  isCreating: boolean
  /** True while a prompt/continue API call is in flight. */
  isSending: boolean
  /** The live activity block, or null if no assistant turn is active. */
  currentActivity: ActivityBlockData | null
  /** Whether the composer should be enabled. */
  composerEnabled: boolean
  /** Whether the cancel button should be shown. */
  cancelVisible: boolean
}
