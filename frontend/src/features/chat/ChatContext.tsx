/**
 * Shared state for the chat mode's multi-column layout.
 *
 * The chat mode renders up to four spawns side-by-side as columns. This
 * context is the single source of truth for which spawns are visible and
 * which column currently has focus (receives keyboard input, highlights
 * in the UI).
 *
 * Column lifecycle:
 * - `openSpawn` adds a spawn as a new column, or focuses it if already open.
 *   When the column cap is reached the least-recently-focused column is
 *   evicted — focus order is tracked via a recency stack so the "LRU"
 *   semantic survives arbitrary focus/open sequences.
 * - `closeColumn` removes a spawn and, if it was focused, hands focus to
 *   the most recently focused surviving column (or null if none remain).
 * - `focusColumn` just updates focus and bumps the recency stack.
 *
 * Outside a `ChatProvider`, `useChat` throws — unlike NavigationContext's
 * console fallback, chat state is meaningless without a provider and a
 * silent stub would mask wiring bugs.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

/** Maximum number of columns that can be open simultaneously. */
export const MAX_COLUMNS = 4

export interface ChatState {
  /** Ordered list of spawn IDs shown as columns. At most {@link MAX_COLUMNS}. */
  columns: string[]
  /** The active/focused column (receives keyboard input). */
  focusedColumn: string | null
}

export interface ChatContextValue {
  state: ChatState
  /** Open a spawn in a new column (or focus existing). */
  openSpawn: (spawnId: string) => void
  /** Close a column. */
  closeColumn: (spawnId: string) => void
  /** Set which column has focus. */
  focusColumn: (spawnId: string) => void
  /** Whether the column cap has been reached. */
  isMaxColumns: boolean
}

export const ChatContext = createContext<ChatContextValue | null>(null)

interface ChatProviderProps {
  children: ReactNode
}

/**
 * Move `spawnId` to the top of the recency stack, removing any prior entry.
 * Most-recently-focused is the first element; least-recently-focused is last.
 */
function bumpRecency(stack: string[], spawnId: string): string[] {
  return [spawnId, ...stack.filter((id) => id !== spawnId)]
}

export function ChatProvider({ children }: ChatProviderProps) {
  const [columns, setColumns] = useState<string[]>([])
  const [focusedColumn, setFocusedColumn] = useState<string | null>(null)
  // Recency stack: most-recently-focused first. Only contains IDs currently
  // in `columns`. Maintained in step with focus changes and column removals.
  // Only the setter is used — we always read via functional updates so the
  // computed state reflects the latest recency even across batched renders.
  const [, setRecency] = useState<string[]>([])

  const openSpawn = useCallback((spawnId: string) => {
    // Drive both `columns` and `recency` from a single functional update
    // so the eviction choice stays consistent across concurrent React
    // renders. We piggyback on `setRecency` as the outer update and nest
    // `setColumns` inside so both observe the same `prevRecency`.
    setRecency((prevRecency) => {
      let nextRecency = prevRecency
      setColumns((prevColumns) => {
        if (prevColumns.includes(spawnId)) {
          // Already open — just re-focus (recency bump below).
          return prevColumns
        }
        if (prevColumns.length < MAX_COLUMNS) {
          return [...prevColumns, spawnId]
        }
        // At capacity: evict least-recently-focused column.
        const evictTarget = prevRecency.at(-1) ?? prevColumns[0]
        nextRecency = prevRecency.filter((id) => id !== evictTarget)
        return [...prevColumns.filter((id) => id !== evictTarget), spawnId]
      })
      return bumpRecency(nextRecency, spawnId)
    })
    setFocusedColumn(spawnId)
  }, [])

  const closeColumn = useCallback((spawnId: string) => {
    setColumns((prev) => {
      if (!prev.includes(spawnId)) return prev
      const next = prev.filter((id) => id !== spawnId)

      setRecency((prevRecency) => {
        const nextRecency = prevRecency.filter((id) => id !== spawnId)
        setFocusedColumn((prevFocus) => {
          if (prevFocus !== spawnId) return prevFocus
          // Closed column had focus — hand off to the most recently
          // focused survivor, or null if none remain.
          return nextRecency[0] ?? null
        })
        return nextRecency
      })

      return next
    })
  }, [])

  const focusColumn = useCallback((spawnId: string) => {
    setColumns((prev) => {
      if (!prev.includes(spawnId)) return prev
      setFocusedColumn(spawnId)
      setRecency((prevRecency) => bumpRecency(prevRecency, spawnId))
      return prev
    })
  }, [])

  const value = useMemo<ChatContextValue>(
    () => ({
      state: { columns, focusedColumn },
      openSpawn,
      closeColumn,
      focusColumn,
      isMaxColumns: columns.length >= MAX_COLUMNS,
    }),
    [columns, focusedColumn, openSpawn, closeColumn, focusColumn],
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
