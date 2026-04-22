// ═══════════════════════════════════════════════════════════════════
// Turn mapper — transforms backend Turn+TurnBlocks into ThreadTurn view models
//
// The backend stores turns with nested blocks; this mapper:
// - For assistant turns: groups tool_use + tool_result by tool_use_id,
//   maps text/thinking blocks, and produces ActivityBlockData
// - For user turns: preserves blocks as TurnBlock[]
// - For system turns: preserves blocks as systemBlocks[]
// ═══════════════════════════════════════════════════════════════════

import type {
  ActivityBlockData,
  ActivityItem,
  ContentItem,
  ThinkingItem,
  ToolItem,
  ToolStatus,
} from "@/features/activity-stream/types"

import type { BackendTurn, BackendTurnBlock } from "./transport-types"
import type {
  AssistantTurn,
  BlockType,
  SystemTurn,
  ThreadTurn,
  TurnBlock,
  TurnRole,
  TurnStatus,
  UserTurn,
} from "./types"

// --- Validation helpers (fix #2: validate network data instead of unsafe `as` casts) ---

const VALID_ROLES = new Set<string>(["user", "assistant", "system"])

function validateRole(role: string): TurnRole {
  if (VALID_ROLES.has(role)) return role as TurnRole
  console.warn(`Unknown turn role: "${role}", defaulting to "user"`)
  return "user"
}

const VALID_STATUSES = new Set<string>([
  "pending",
  "streaming",
  "waiting_subagents",
  "complete",
  "cancelled",
  "error",
  "credit_limited",
])

function validateStatus(status: string): TurnStatus {
  if (VALID_STATUSES.has(status)) return status as TurnStatus
  console.warn(`Unknown turn status: "${status}", defaulting to "complete"`)
  return "complete"
}

const VALID_BLOCK_TYPES = new Set<string>([
  "text",
  "thinking",
  "tool_use",
  "tool_result",
  "image",
  "reference",
  "partial_reference",
  "web_search_use",
  "web_search_result",
  "collapse_marker",
])

function validateBlockType(blockType: string): BlockType {
  if (VALID_BLOCK_TYPES.has(blockType)) return blockType as BlockType
  console.warn(`Unknown block type: "${blockType}", defaulting to "text"`)
  return "text"
}

// --- Terminal status helper (fix #5) ---

const TERMINAL_STATUSES = new Set<string>(["complete", "cancelled", "error", "credit_limited"])

// --- Block mapping (backend snake_case → frontend camelCase) ---

function mapBlock(b: BackendTurnBlock): TurnBlock {
  return {
    id: b.id,
    blockType: validateBlockType(b.block_type),
    sequence: b.sequence,
    textContent: b.text_content ?? undefined,
    content: b.content ?? undefined,
    status: b.status === "partial" ? "partial" : "complete",
  }
}

// --- Tool pairing helpers ---

/**
 * Safely extract tool_use_id from a block's content JSONB.
 * Returns undefined (with a warning) if the field is missing or not a string. (fix #6)
 */
function extractToolUseId(block: BackendTurnBlock): string | undefined {
  const content = block.content as Record<string, unknown> | undefined | null
  if (!content) return undefined
  const toolUseId = content.tool_use_id
  if (typeof toolUseId === "string") return toolUseId
  return undefined
}

/**
 * Determine ToolStatus from the paired blocks.
 * - Has result block → "done" or "error"
 * - Use block is partial (interrupted stream) → "error"
 * - Parent turn is terminal (cancelled/error/credit_limited) → "error" (fix #5)
 * - Otherwise → "executing" (result hasn't arrived yet, e.g. persisted mid-stream)
 */
function resolveToolStatus(
  resultBlock: BackendTurnBlock | undefined,
  useBlock: BackendTurnBlock,
  isTurnTerminal: boolean,
): ToolStatus {
  if (resultBlock) {
    const resultContent = resultBlock.content as Record<string, unknown> | undefined | null
    return resultContent?.is_error ? "error" : "done"
  }
  // No result yet — check if the use block was interrupted
  if (useBlock.status === "partial") {
    return "error"
  }
  // Orphaned tool_use on a terminal turn → mark as error, not executing (fix #5)
  if (isTurnTerminal) {
    return "error"
  }
  return "executing"
}

/**
 * Extract result text from a tool_result block's content JSONB.
 *
 * Backend stores tool results in content.result (success) and content.error (error).
 * Falls back to text_content if content fields are missing (defensive). (fix #3)
 */
/** Safely stringify a value that may be a string, object, or other type. */
function stringifyValue(value: unknown): string | undefined {
  if (value == null) return undefined
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function extractToolResultText(
  resultBlock: BackendTurnBlock,
): { resultText: string | undefined; isError: boolean } {
  const resultContent = resultBlock.content as
    | { tool_use_id?: string; is_error?: boolean; result?: unknown; error?: unknown }
    | undefined
    | null

  const isError = resultContent?.is_error ?? false

  if (isError) {
    const resultText = stringifyValue(resultContent?.error) ?? resultBlock.text_content ?? undefined
    return { resultText, isError }
  }

  // result can be a string or structured object (e.g. doc_search, web_search return maps)
  const resultText = stringifyValue(resultContent?.result) ?? resultBlock.text_content ?? undefined
  return { resultText, isError }
}

// --- Assistant turn → ActivityBlockData ---

/**
 * Map assistant turn blocks into ActivityItem[].
 *
 * Pairs tool_use + tool_result blocks by tool_use_id.
 * Web search blocks (web_search_use + web_search_result) follow the same
 * tool pairing pattern — they carry tool_use_id just like regular tools.
 */
export function mapBlocksToActivityItems(
  blocks: BackendTurnBlock[],
  isTurnTerminal: boolean,
): ActivityItem[] {
  // Index tool_result and web_search_result blocks by tool_use_id for O(1) pairing
  const resultByToolUseId = new Map<string, BackendTurnBlock>()
  for (const b of blocks) {
    if (b.block_type === "tool_result" || b.block_type === "web_search_result") {
      const toolUseId = extractToolUseId(b)
      if (toolUseId) {
        resultByToolUseId.set(toolUseId, b)
      }
    }
  }

  const items: ActivityItem[] = []

  for (const b of blocks) {
    switch (b.block_type) {
      case "text": {
        if (b.text_content) {
          const item: ContentItem = {
            kind: "content",
            id: b.id,
            text: b.text_content,
          }
          items.push(item)
        }
        break
      }

      case "thinking": {
        // Skip whitespace-only thinking blocks (matches backend FilterWhitespaceOnlyThinkingBlocks)
        if (!b.text_content || b.text_content.trim() === "") {
          break
        }
        const item: ThinkingItem = {
          kind: "thinking",
          id: b.id,
          text: b.text_content,
        }
        items.push(item)
        break
      }

      case "tool_use":
      case "web_search_use": {
        // Defensive: validate tool_use_id exists before pairing (fix #6)
        const toolUseId = extractToolUseId(b)
        if (!toolUseId) {
          console.warn(`${b.block_type} block ${b.id} missing tool_use_id, creating fallback item`)
          // Create a fallback ToolItem so the UI still shows something
          const item: ToolItem = {
            kind: "tool",
            id: b.id,
            toolName: undefined,
            status: "error",
            argsText: "",
            isError: true,
            resultText: "Missing tool_use_id",
          }
          items.push(item)
          break
        }

        const content = b.content as Record<string, unknown> | undefined | null
        const toolName = typeof content?.tool_name === "string" ? content.tool_name : undefined
        const input =
          content?.input && typeof content.input === "object"
            ? (content.input as Record<string, unknown>)
            : undefined

        const resultBlock = resultByToolUseId.get(toolUseId)
        const status = resolveToolStatus(resultBlock, b, isTurnTerminal)

        // Extract result text from content JSONB, not text_content (fix #3)
        const { resultText, isError } = resultBlock
          ? extractToolResultText(resultBlock)
          : { resultText: undefined, isError: false }

        const item: ToolItem = {
          kind: "tool",
          id: b.id,
          toolName,
          status,
          argsText: input ? JSON.stringify(input) : "",
          parsedArgs: input ?? undefined,
          resultText,
          isError,
        }
        items.push(item)
        break
      }

      // tool_result / web_search_result are consumed by the tool_use pairing above.
      // Skip them as standalone items — they're folded into their ToolItem.
      case "tool_result":
      case "web_search_result":
        break

      // image, reference, partial_reference — not mapped to ActivityItems for now.
      // Phase 5 will add dedicated item kinds for these.
      // They're still available on the ThreadTurn.blocks for user turns.
      default:
        break
    }
  }

  return items
}

// --- Main mapper ---

/**
 * Map a backend Turn (with nested blocks) into a ThreadTurn view model.
 *
 * - Assistant turns → blocks converted to ActivityBlockData
 * - User turns → blocks preserved as TurnBlock[]
 * - System turns → blocks preserved as systemBlocks[]
 */
export function mapTurnToViewModel(turn: BackendTurn): ThreadTurn {
  const role = validateRole(turn.role)
  const status = validateStatus(turn.status)
  const blocks = turn.blocks ?? []
  const sortedBlocks = [...blocks].sort((a, b) => a.sequence - b.sequence)

  // Compute sibling index (position of this turn within its siblings)
  const siblingIds = turn.sibling_ids ?? []
  const idx = siblingIds.indexOf(turn.id)
  if (idx === -1) {
    // fix #8: warn when turn is not found in its own sibling_ids
    console.warn(`Turn ${turn.id} not found in its own sibling_ids`)
  }
  const siblingIndex = Math.max(0, idx)

  const base = {
    id: turn.id,
    threadId: turn.thread_id,
    parentId: turn.prev_turn_id ?? null,
    status,
    siblingIds,
    siblingIndex,
    createdAt: new Date(turn.created_at),
    model: turn.model ?? undefined,
    inputTokens: turn.input_tokens ?? undefined,
    outputTokens: turn.output_tokens ?? undefined,
    error: turn.error ?? undefined,
  }

  switch (role) {
    case "assistant": {
      const isTurnTerminal = TERMINAL_STATUSES.has(status)
      const activityItems = mapBlocksToActivityItems(sortedBlocks, isTurnTerminal)
      const isStreaming = status === "streaming" || status === "pending"

      const activity: ActivityBlockData = {
        id: turn.id,
        items: activityItems,
        isStreaming,
        error: status === "error" ? (turn.error ?? "Unknown error") : undefined,
        isCancelled: status === "cancelled" ? true : undefined,
      }

      return { ...base, role: "assistant", activity } satisfies AssistantTurn
    }

    case "user": {
      return { ...base, role: "user", blocks: sortedBlocks.map(mapBlock) } satisfies UserTurn
    }

    case "system": {
      // fix #4: preserve request_params.turn_type for system turns
      const turnType =
        typeof (turn.request_params as Record<string, unknown> | undefined | null)?.turn_type ===
        "string"
          ? ((turn.request_params as Record<string, unknown>).turn_type as string)
          : undefined

      return {
        ...base,
        role: "system",
        systemBlocks: sortedBlocks.map(mapBlock),
        turnType,
      } satisfies SystemTurn
    }

    default: {
      // Defensive — treat unknown roles as system (validateRole already warned)
      return {
        ...base,
        role: "system",
        systemBlocks: sortedBlocks.map(mapBlock),
      } satisfies SystemTurn
    }
  }
}

/**
 * Map a paginated response of backend turns into ThreadTurn view models.
 * Preserves order from the backend (typically oldest → newest along the active path).
 */
export function mapTurnsToViewModels(turns: BackendTurn[]): ThreadTurn[] {
  return turns.map(mapTurnToViewModel)
}
