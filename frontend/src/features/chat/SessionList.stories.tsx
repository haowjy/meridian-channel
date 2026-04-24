import type { Meta, StoryObj } from "@storybook/react-vite"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { SpawnProjection, ChatProjection } from "@/features/sessions/lib/api"

import { ChatProvider } from "./ChatContext"
import { SessionList } from "./SessionList"

/**
 * Stories pin `dataOverride` so live hooks never hit the network.
 * The component still mounts inside a `ChatProvider` (its `useChat`
 * call requires one) but the override bypasses the chat context.
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

const CHATS: ChatProjection[] = [
  {
    chat_id: "c001",
    state: "active",
    title: "Build the login page",
    model: "opus-4-7",
    active_p_id: "p201",
    created_at: iso(-2 * 60_000),
    updated_at: iso(-30_000),
  },
  {
    chat_id: "c002",
    state: "idle",
    title: "Review auth middleware",
    model: "sonnet-4-6",
    active_p_id: null,
    created_at: iso(-20 * 60_000),
    updated_at: iso(-15 * 60_000),
  },
  {
    chat_id: "c003",
    state: "draining",
    title: "Fix Windows path issue",
    model: "opus-4-7",
    active_p_id: "p301",
    created_at: iso(-45 * 60_000),
    updated_at: iso(-5 * 60_000),
  },
  {
    chat_id: "c004",
    state: "closed",
    title: "Initial project setup",
    model: "sonnet-4-6",
    active_p_id: null,
    created_at: iso(-3 * 3600_000),
    updated_at: iso(-2 * 3600_000),
  },
]

const SPAWNS: SpawnProjection[] = [
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
    spawn_id: "p301",
    status: "running",
    agent: "frontend-coder",
    desc: "Restyle metrics cards",
    started_at: iso(-12 * 60_000),
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
    spawn_id: "p204",
    status: "failed",
    agent: "verifier",
    desc: "Run typecheck + tests",
    started_at: iso(-55 * 60_000),
    finished_at: iso(-50 * 60_000),
  }),
]

const logSelect = (id: string) => {
  // eslint-disable-next-line no-console
  console.log("[story] select spawn", id)
}

const logSelectChat = (id: string, state: string) => {
  // eslint-disable-next-line no-console
  console.log("[story] select chat", id, state)
}

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

export const WithChatsAndSpawns: Story = {
  args: {
    dataOverride: {
      chats: CHATS,
      spawns: SPAWNS,
      onSelectChat: logSelectChat,
      onSelectSpawn: logSelect,
    },
  },
}

export const ChatsOnly: Story = {
  args: {
    dataOverride: {
      chats: CHATS,
      spawns: [],
      onSelectChat: logSelectChat,
    },
  },
}

export const SpawnsOnly: Story = {
  args: {
    dataOverride: {
      chats: [],
      spawns: SPAWNS,
      onSelectSpawn: logSelect,
    },
  },
}

export const Empty: Story = {
  args: {
    dataOverride: {
      chats: [],
      spawns: [],
    },
  },
}

export const Loading: Story = {
  args: {
    dataOverride: {
      chats: [],
      spawns: [],
      isLoading: true,
    },
  },
}

export const ErrorState: Story = {
  name: "Error",
  args: {
    dataOverride: {
      chats: [],
      spawns: [],
      error: "ECONNREFUSED http://localhost:7707/api/chats",
    },
  },
}

export const SelectedChat: Story = {
  args: {
    dataOverride: {
      chats: CHATS,
      spawns: SPAWNS,
      selectedChatId: "c001",
      onSelectChat: logSelectChat,
      onSelectSpawn: logSelect,
    },
  },
}

export const WithActiveColumns: Story = {
  args: {
    dataOverride: {
      chats: CHATS,
      spawns: SPAWNS,
      activeColumns: ["p301", "p202", "p501"],
      focusedColumn: "p202",
      onSelectChat: logSelectChat,
      onSelectSpawn: logSelect,
    },
  },
}
