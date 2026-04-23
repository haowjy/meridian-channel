import type { Meta, StoryObj } from "@storybook/react-vite"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { SpawnProjection } from "@/features/sessions/lib/api"

import { ChatPage } from "./ChatPage"
import type { ThreadColumnSpawnDetails } from "./ThreadColumn"

/**
 * Stories pin both the session-list data source and per-column spawn
 * details via overrides so nothing touches the network. `ThreadColumn`
 * still opens a websocket internally — Storybook just lets it fail and
 * the column renders its idle empty state, which is representative of
 * the first-paint experience before frames arrive.
 */

const meta: Meta<typeof ChatPage> = {
  title: "Features/Chat/ChatPage",
  component: ChatPage,
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story) => (
      // Pin the page to the viewport so flex-based layouts resolve.
      // Borders above/below match the real AppShell chrome context.
      <TooltipProvider>
        <div className="flex h-screen w-full flex-col bg-background">
          <div className="min-h-0 flex-1 border-y border-border">
            <Story />
          </div>
        </div>
      </TooltipProvider>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof ChatPage>

// ---------------------------------------------------------------------------
// Mock factories
// ---------------------------------------------------------------------------

const NOW = Date.parse("2026-04-22T10:30:00Z")

function iso(offsetMs: number): string {
  return new Date(NOW + offsetMs).toISOString()
}

function makeSpawn(overrides: Partial<SpawnProjection> = {}): SpawnProjection {
  return {
    spawn_id: "p100",
    status: "running",
    harness: "claude",
    model: "opus-4-7",
    agent: "coder",
    work_id: null,
    desc: "Placeholder spawn",
    created_at: iso(-5 * 60_000),
    started_at: iso(-5 * 60_000 + 500),
    finished_at: null,
    ...overrides,
  }
}

const SPAWNS: SpawnProjection[] = [
  makeSpawn({
    spawn_id: "p1019",
    status: "running",
    agent: "frontend-coder",
    desc: "Chat mode layout polish",
    started_at: iso(-3 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p1024",
    status: "running",
    agent: "coder",
    desc: "Subphase 4 — ChatPage + manifest",
    started_at: iso(-90_000),
  }),
  makeSpawn({
    spawn_id: "p838",
    status: "running",
    agent: "reviewer",
    desc: "Windows-compat review",
    started_at: iso(-6 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p1023",
    status: "finalizing",
    agent: "design-writer",
    desc: "Trim design scope",
    started_at: iso(-2 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p945",
    status: "succeeded",
    agent: "planner",
    desc: "Sparse output plan",
    started_at: iso(-45 * 60_000),
    finished_at: iso(-30 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p617",
    status: "queued",
    agent: "verifier",
    desc: "Typecheck + tests",
    started_at: iso(-10 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p606",
    status: "failed",
    agent: "smoke-tester",
    desc: "CLI smoke — windows",
    started_at: iso(-90 * 60_000),
    finished_at: iso(-80 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p770",
    status: "cancelled",
    agent: "explorer",
    desc: "Scan orphaned refs",
    started_at: iso(-3 * 3600_000),
    finished_at: iso(-2.9 * 3600_000),
  }),
]

const THREAD_DETAILS: Record<string, ThreadColumnSpawnDetails> = {
  p1019: {
    status: "running",
    agent: "frontend-coder",
    model: "opus-4-7",
    harness: "claude",
  },
  p1024: {
    status: "running",
    agent: "coder",
    model: "opus-4-7",
    harness: "claude",
  },
  p838: {
    status: "running",
    agent: "reviewer",
    model: "sonnet-4-6",
    harness: "claude",
  },
  p1023: {
    status: "finalizing",
    agent: "design-writer",
    model: "sonnet-4-6",
    harness: "claude",
  },
  p617: {
    status: "queued",
    agent: "verifier",
    model: null,
    harness: "codex",
  },
}

const baseArgs = {
  sessionListOverride: {
    spawns: SPAWNS,
  },
  threadDetailsOverride: THREAD_DETAILS,
} satisfies Partial<React.ComponentProps<typeof ChatPage>>

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    ...baseArgs,
    initialSpawnId: "p1019",
  },
}

export const MultiColumn: Story = {
  args: {
    ...baseArgs,
    initialColumns: ["p1019", "p1024"],
    initialFocus: "p1024",
  },
}

export const Empty: Story = {
  args: {
    ...baseArgs,
    initialSpawnId: null,
  },
}

export const MaxColumns: Story = {
  args: {
    ...baseArgs,
    initialColumns: ["p1019", "p1024", "p838", "p1023"],
    initialFocus: "p1019",
  },
}

export const CollapsedSidebar: Story = {
  args: {
    ...baseArgs,
    initialColumns: ["p1019", "p1024"],
    initialFocus: "p1019",
    initialSidebarCollapsed: true,
  },
}
