import type { Meta, StoryObj } from "@storybook/react-vite"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { SpawnProjection } from "@/features/sessions/lib/api"

import { ChatProvider } from "./ChatContext"
import { SessionList } from "./SessionList"

/**
 * Stories pin `dataOverride` so the live `useSessions` hook never hits the
 * network. The component still mounts inside a `ChatProvider` (its
 * `useChat` call requires one) but the override also bypasses the chat
 * context for active-column rendering.
 */

const meta: Meta<typeof SessionList> = {
  title: "Features/Chat/SessionList",
  component: SessionList,
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story) => (
      <TooltipProvider>
        <ChatProvider>
          <div className="flex h-[640px] border-t border-border">
            <Story />
            <div className="flex-1 bg-muted/20" />
          </div>
        </ChatProvider>
      </TooltipProvider>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof SessionList>

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

const POPULATED_SPAWNS: SpawnProjection[] = [
  makeSpawn({
    spawn_id: "p201",
    status: "running",
    agent: "coder",
    desc: "Implement auth middleware",
    started_at: iso(-2 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p202",
    status: "queued",
    agent: "reviewer",
    desc: "Review auth handoff",
    started_at: iso(-90_000),
  }),
  makeSpawn({
    spawn_id: "p205",
    status: "finalizing",
    agent: "coder",
    desc: "Apply review fixes",
    started_at: iso(-4 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p301",
    status: "running",
    agent: "frontend-coder",
    desc: "Restyle metrics cards",
    started_at: iso(-12 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p304",
    status: "running",
    agent: "coder",
    desc: "Wire live stats hook",
    started_at: iso(-25 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p501",
    status: "running",
    agent: "explorer",
    desc: "Scan repo for orphaned TODOs",
    started_at: iso(-6 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p203",
    status: "succeeded",
    agent: "planner",
    desc: "Draft phase plan",
    started_at: iso(-30 * 60_000),
    finished_at: iso(-25 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p302",
    status: "succeeded",
    agent: "frontend-designer",
    desc: "Ship spec revisions",
    started_at: iso(-2 * 3600_000),
    finished_at: iso(-90 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p204",
    status: "failed",
    agent: "verifier",
    desc: "Run typecheck + tests",
    started_at: iso(-55 * 60_000),
    finished_at: iso(-50 * 60_000),
  }),
  makeSpawn({
    spawn_id: "p303",
    status: "cancelled",
    agent: "browser-tester",
    desc: "Smoke test filter bar",
    started_at: iso(-3 * 3600_000),
    finished_at: iso(-2.5 * 3600_000),
  }),
]

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

export const Populated: Story = {
  args: {
    dataOverride: {
      spawns: POPULATED_SPAWNS,
      onSelect: (id) => {
        // eslint-disable-next-line no-console
        console.log("[story] open", id)
      },
    },
  },
}

export const Empty: Story = {
  args: {
    dataOverride: {
      spawns: [],
    },
  },
}

export const Loading: Story = {
  args: {
    dataOverride: {
      spawns: [],
      isLoading: true,
    },
  },
}

export const ErrorState: Story = {
  name: "Error",
  args: {
    dataOverride: {
      spawns: [],
      error: "ECONNREFUSED http://localhost:7707/api/spawns/list",
    },
  },
}

export const Scrolling: Story = {
  args: {
    dataOverride: {
      spawns: Array.from({ length: 40 }).map<SpawnProjection>((_, i) =>
        makeSpawn({
          spawn_id: `p${600 + i}`,
          status: (
            ["running", "queued", "succeeded", "failed", "cancelled", "finalizing"] as const
          )[i % 6],
          agent: ["coder", "reviewer", "planner", "verifier", "explorer", "smoke-tester"][i % 6],
          desc: `Long-running task #${i + 1} with a description that may be truncated`,
          started_at: iso(-(i + 1) * 90_000),
          finished_at: i % 6 === 2 ? iso(-(i + 1) * 60_000) : null,
        }),
      ),
      onSelect: (id) => {
        // eslint-disable-next-line no-console
        console.log("[story] open", id)
      },
    },
  },
}

export const WithActiveColumns: Story = {
  args: {
    dataOverride: {
      spawns: POPULATED_SPAWNS,
      activeColumns: ["p301", "p202", "p501"],
      focusedColumn: "p202",
      onSelect: (id) => {
        // eslint-disable-next-line no-console
        console.log("[story] open", id)
      },
    },
  },
}
