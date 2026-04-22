// ═══════════════════════════════════════════════════════════════════
// Thread data model — mirrors backend Turn + TurnBlock domain types
//
// These are the frontend view models. Backend JSON responses are mapped
// through turn-mapper.ts before landing here.
// ═══════════════════════════════════════════════════════════════════

import type { ActivityBlockData } from "@/features/activity-stream/types"

// --- Enums matching backend constants (turn.go, turn_block.go) ---

export type TurnRole = "user" | "assistant" | "system"

export type TurnStatus =
  | "pending"
  | "streaming"
  | "waiting_subagents"
  | "complete"
  | "cancelled"
  | "error"
  | "credit_limited"

export type BlockType =
  | "text"
  | "thinking"
  | "tool_use"
  | "tool_result"
  | "image"
  | "reference"
  | "partial_reference"
  | "web_search_use"
  | "web_search_result"
  | "collapse_marker"

export type BlockStatus = "complete" | "partial"

// --- TurnBlock — normalized frontend representation of backend TurnBlock ---

/**
 * Mirrors backend TurnBlock. Keeps all fields the UI may need.
 *
 * Content JSONB is typed per block type:
 * - tool_use:    { tool_use_id, tool_name, input }
 * - tool_result: { tool_use_id, is_error }
 * - image:       { url, mime_type, alt_text }
 * - reference:   { ref_id, ref_type, selection_start, ... }
 * - web_search_use:    { tool_use_id, tool_name, input }
 * - web_search_result: { tool_use_id, results: [...] } or { tool_use_id, is_error, error_code }
 * - text/thinking: null (text lives in textContent)
 */
export type TurnBlock = {
  id: string
  blockType: BlockType
  sequence: number
  textContent?: string
  content?: Record<string, unknown>
  status?: BlockStatus
}

// --- ThreadTurn — discriminated union on role ---

/**
 * Base fields shared by all turn roles.
 *
 * Tree structure via parentId + siblingIds enables branching conversations.
 */
type ThreadTurnBase = {
  id: string
  threadId: string
  /** prevTurnId — links to parent in the turn tree */
  parentId: string | null
  status: TurnStatus
  siblingIds: string[]
  siblingIndex: number
  createdAt: Date

  // Metadata
  model?: string
  inputTokens?: number
  outputTokens?: number
  error?: string
}

/** Assistant turns: activity holds the full ActivityBlockData (tools, thinking, content) */
export type AssistantTurn = ThreadTurnBase & {
  role: "assistant"
  activity: ActivityBlockData
}

/** User turns: blocks holds the raw TurnBlock[] (text, images, references, tool_results) */
export type UserTurn = ThreadTurnBase & {
  role: "user"
  blocks: TurnBlock[]
}

/** System turns: systemBlocks holds bookmark blocks (compaction, collapse_marker) */
export type SystemTurn = ThreadTurnBase & {
  role: "system"
  systemBlocks: TurnBlock[]
  /** From request_params.turn_type — e.g. "compaction", "collapse" */
  turnType?: string
}

/**
 * A single turn in a conversation thread — discriminated union on `role`.
 *
 * Consumers narrow via `turn.role`:
 *   if (turn.role === "assistant") turn.activity.items  // no optional chaining needed
 */
export type ThreadTurn = AssistantTurn | UserTurn | SystemTurn

// --- Active path — the selected branch through the turn tree ---

export type ActivePath = {
  /** Ordered turn IDs forming the current conversation path */
  turnIds: string[]
  /** Map of parentId → selected childId for branch points */
  selectedSiblings: Record<string, string>
}

// --- Thread — top-level conversation container ---

export type Thread = {
  id: string
  projectId: string
  title: string
  lastViewedTurnId?: string
  createdAt: Date
}
