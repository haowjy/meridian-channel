/**
 * ChatPage — top-level view for Chat mode.
 *
 * Composes the sidebar `SessionList` with a column area that renders up to
 * {@link MAX_COLUMNS} `ThreadColumn`s side-by-side. Column state lives in
 * {@link ChatProvider}; this component is a thin shell that wires layout,
 * the sidebar collapse toggle, and the `initialSpawnId` mount behaviour.
 *
 * Layout choices:
 * - Columns evenly split available width via a CSS grid (`repeat(N, 1fr)`).
 *   `minmax(0, 1fr)` prevents content from pushing a column past its share.
 * - A slim chrome bar above the grid holds the sidebar toggle and a compact
 *   capacity indicator. It stays present even when the sidebar is expanded
 *   so the toggle control doesn't jump around.
 * - The empty state is a deliberately quiet composition — hairline frame,
 *   muted glyph, uppercase tracking — matching the tone of the SessionList
 *   header rather than a loud hero treatment.
 *
 * The `initialSpawnId` prop is honoured once per mount; subsequent changes
 * to the prop don't re-open the spawn (that belongs to the caller that's
 * navigating). Storybook pins overrides on `SessionList`/`ThreadColumn` so
 * stories never touch the network.
 */

import { useEffect, useState } from "react"
import { ChatCircle, List, SidebarSimple } from "@phosphor-icons/react"

import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { useNavigation } from "@/shell/NavigationContext"

import { ChatProvider, MAX_COLUMNS, useChat } from "./ChatContext"
import { SessionList, type SessionListDataOverride } from "./SessionList"
import {
  ThreadColumn,
  type ThreadColumnSpawnDetails,
} from "./ThreadColumn"

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface ChatPageProps {
  /**
   * Spawn to open on mount. Honoured once per ChatProvider instance.
   * Subsequent changes are ignored — if you need to switch spawns, call
   * `openSpawn` via `useChat` or remount with a new provider.
   */
  initialSpawnId?: string | null
  className?: string
  /**
   * Storybook/test override for the session list data source.
   * When provided, forwards to {@link SessionList}.
   */
  sessionListOverride?: SessionListDataOverride
  /**
   * Storybook/test override for per-column spawn identity. Keyed by
   * spawn id; columns without a matching entry fall back to the live
   * fetch in {@link ThreadColumn}.
   */
  threadDetailsOverride?: Record<string, ThreadColumnSpawnDetails>
  /**
   * Storybook/test override: pre-open these spawn ids as columns and
   * pin the first one as focused. Applied once on mount.
   */
  initialColumns?: readonly string[]
  /**
   * Storybook/test override: pin the focused column on mount. Must match
   * one of `initialColumns` or `initialSpawnId`.
   */
  initialFocus?: string
  /**
   * Storybook/test override: start with the sidebar collapsed.
   */
  initialSidebarCollapsed?: boolean
}

// ---------------------------------------------------------------------------
// Entry point — supplies the provider, delegates to <ChatPageContent />.
// ---------------------------------------------------------------------------

export function ChatPage(props: ChatPageProps) {
  return (
    <ChatProvider>
      <ChatPageContent {...props} />
    </ChatProvider>
  )
}

// ---------------------------------------------------------------------------
// Inner layout
// ---------------------------------------------------------------------------

function ChatPageContent({
  initialSpawnId,
  className,
  sessionListOverride,
  threadDetailsOverride,
  initialColumns,
  initialFocus,
  initialSidebarCollapsed,
}: ChatPageProps) {
  const { state, openSpawn, closeColumn, focusColumn } = useChat()
  const { pendingChatSpawnId, clearPendingChatSpawnId } = useNavigation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    Boolean(initialSidebarCollapsed),
  )

  // Open the initial spawn — and any storybook-seeded columns — exactly once.
  // `openSpawn` is stable (useCallback with empty deps inside ChatProvider),
  // but we guard with an effect-scoped "done" flag so a parent re-render
  // can't accidentally reopen them.
  useEffect(() => {
    const seeds: string[] = []
    if (initialColumns) seeds.push(...initialColumns)
    if (initialSpawnId && !seeds.includes(initialSpawnId)) seeds.push(initialSpawnId)
    for (const id of seeds) openSpawn(id)
    if (initialFocus) focusColumn(initialFocus)
    // Intentional: run once on mount. initialSpawnId / initialColumns are a
    // launch hint, not a reactive binding.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Cross-mode navigation handoff: AppShell stashes a spawn id into
  // NavigationContext when navigateToChat fires. Consume it here (on mount
  // or whenever a new id arrives), then clear so the same id can't be
  // re-opened on an unrelated re-render. Subsequent navigateToChat calls
  // after mount still land — openSpawn is idempotent (no-op if the column
  // is already open) and focuses the matching column.
  useEffect(() => {
    if (!pendingChatSpawnId) return
    openSpawn(pendingChatSpawnId)
    clearPendingChatSpawnId()
  }, [pendingChatSpawnId, openSpawn, clearPendingChatSpawnId])

  const columnCount = state.columns.length

  return (
    <div
      className={cn(
        "relative flex h-full min-h-0 w-full overflow-hidden bg-background",
        className,
      )}
    >
      <aside
        className={cn(
          "relative h-full shrink-0 overflow-hidden",
          "transition-[width] duration-200 ease-out",
          sidebarCollapsed ? "w-0" : "w-60",
        )}
        aria-hidden={sidebarCollapsed}
      >
        {/* SessionList is fixed-width (w-60) internally; keeping it mounted
            while the aside collapses preserves scroll position and avoids a
            remount flash when the user re-expands. */}
        <div className="absolute inset-y-0 right-0 w-60">
          <SessionList dataOverride={sessionListOverride} />
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <ColumnAreaChrome
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
          columnCount={columnCount}
        />

        {columnCount === 0 ? (
          <EmptyColumnState sidebarCollapsed={sidebarCollapsed} />
        ) : (
          <div
            className="grid min-h-0 flex-1 gap-2 p-2"
            style={{
              gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`,
            }}
          >
            {state.columns.map((spawnId) => (
              <ThreadColumn
                key={spawnId}
                spawnId={spawnId}
                isFocused={state.focusedColumn === spawnId}
                onClose={() => closeColumn(spawnId)}
                onFocus={() => focusColumn(spawnId)}
                detailsOverride={threadDetailsOverride?.[spawnId]}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chrome bar (sidebar toggle + capacity indicator)
// ---------------------------------------------------------------------------

interface ColumnAreaChromeProps {
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  columnCount: number
}

function ColumnAreaChrome({
  sidebarCollapsed,
  onToggleSidebar,
  columnCount,
}: ColumnAreaChromeProps) {
  const ToggleIcon = sidebarCollapsed ? List : SidebarSimple
  const tooltip = sidebarCollapsed ? "Show sessions" : "Hide sessions"

  return (
    <div className="flex h-9 items-center justify-between border-b border-border/60 pl-1 pr-3">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={onToggleSidebar}
            aria-label={tooltip}
            aria-pressed={!sidebarCollapsed}
            className="text-muted-foreground hover:text-foreground"
          >
            <ToggleIcon weight="regular" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">{tooltip}</TooltipContent>
      </Tooltip>

      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground/70">
          Columns
        </span>
        <CapacityDots count={columnCount} />
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
          {columnCount}/{MAX_COLUMNS}
        </span>
      </div>
    </div>
  )
}

function CapacityDots({ count }: { count: number }) {
  return (
    <div className="flex items-center gap-1" aria-hidden>
      {Array.from({ length: MAX_COLUMNS }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "h-1.5 w-1.5 rounded-full transition-colors",
            i < count ? "bg-accent-fill" : "bg-border",
          )}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyColumnState({ sidebarCollapsed }: { sidebarCollapsed: boolean }) {
  return (
    <div className="relative flex min-h-0 flex-1 items-center justify-center p-8">
      {/* Hairline grid backdrop — quiet texture that disappears at a glance
          but keeps the empty state from reading as a flat blank canvas. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage:
            "radial-gradient(ellipse at center, black 30%, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, black 30%, transparent 80%)",
        }}
      />

      <div className="relative flex max-w-sm flex-col items-center text-center">
        <div
          className={cn(
            "mb-5 flex size-14 items-center justify-center rounded-full",
            "border border-border/70 bg-background/80 text-muted-foreground/70",
            "shadow-[0_1px_0_var(--border)] backdrop-blur",
          )}
        >
          <ChatCircle weight="duotone" className="size-7" />
        </div>

        <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.22em] text-muted-foreground/70">
          No column selected
        </p>
        <h2 className="mb-2 text-lg font-semibold tracking-tight text-foreground">
          Pick a session to start chatting
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {sidebarCollapsed ? (
            <>
              Re-open the sidebar or switch to Sessions mode to choose a
              spawn. Up to {MAX_COLUMNS} spawns can run side by side.
            </>
          ) : (
            <>
              Select a session from the list, or head to Sessions mode for
              the full filter surface. Up to {MAX_COLUMNS} spawns can run
              side by side.
            </>
          )}
        </p>
      </div>
    </div>
  )
}
