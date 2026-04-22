import type { Meta, StoryObj } from "@storybook/react-vite"
import { WorkItemGroupHeader, WorkItemGroupHeaderSkeleton } from "./WorkItemGroupHeader"
import { SessionRow } from "./SessionRow"
import type { SpawnSummary } from "@/types/spawn"

const meta: Meta<typeof WorkItemGroupHeader> = {
  title: "Components/Molecules/WorkItemGroupHeader",
  component: WorkItemGroupHeader,
  parameters: {
    layout: "padded",
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl border rounded-md overflow-hidden">
        <Story />
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof WorkItemGroupHeader>

// Mock spawns
const mockSpawns: SpawnSummary[] = [
  {
    spawn_id: "p281",
    status: "running",
    agent: "coder",
    model: "claude-sonnet-4",
    harness: "claude",
    work_id: "auth-refactor",
    desc: "Implement authentication middleware",
    started_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    finished_at: null,
    cost_usd: 0.42,
  },
  {
    spawn_id: "p280",
    status: "succeeded",
    agent: "reviewer",
    model: "claude-sonnet-4",
    harness: "claude",
    work_id: "auth-refactor",
    desc: "Review session management changes",
    started_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    finished_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    cost_usd: 0.18,
  },
  {
    spawn_id: "p279",
    status: "succeeded",
    agent: "coder",
    model: "claude-sonnet-4",
    harness: "claude",
    work_id: "auth-refactor",
    desc: "Add JWT validation",
    started_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    finished_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    cost_usd: 0.35,
  },
]

export const Default: Story = {
  args: {
    name: "auth-refactor",
    spawnCount: 3,
    lastActivity: new Date(Date.now() - 5 * 60 * 1000),
    defaultOpen: true,
    children: (
      <div className="flex flex-col">
        {mockSpawns.map((spawn) => (
          <SessionRow
            key={spawn.spawn_id}
            spawn={spawn}
            onClick={() => console.log(`Clicked ${spawn.spawn_id}`)}
          />
        ))}
      </div>
    ),
  },
}

export const Collapsed: Story = {
  args: {
    name: "auth-refactor",
    spawnCount: 3,
    lastActivity: new Date(Date.now() - 5 * 60 * 1000),
    defaultOpen: false,
    children: (
      <div className="flex flex-col">
        {mockSpawns.map((spawn) => (
          <SessionRow
            key={spawn.spawn_id}
            spawn={spawn}
            onClick={() => console.log(`Clicked ${spawn.spawn_id}`)}
          />
        ))}
      </div>
    ),
  },
}

export const Empty: Story = {
  args: {
    name: "empty-work-item",
    spawnCount: 0,
    defaultOpen: true,
    children: (
      <div className="px-3 py-4 text-center text-sm text-muted-foreground">
        No sessions yet
      </div>
    ),
  },
}

export const LongName: Story = {
  args: {
    name: "this-is-a-very-long-work-item-name-that-should-be-truncated-properly",
    spawnCount: 5,
    lastActivity: new Date(Date.now() - 2 * 60 * 60 * 1000),
    defaultOpen: true,
    children: (
      <div className="flex flex-col">
        <SessionRow
          spawn={mockSpawns[0]}
          onClick={() => console.log("Clicked")}
        />
      </div>
    ),
  },
}

export const MultipleGroups: Story = {
  render: () => (
    <div className="flex flex-col">
      <WorkItemGroupHeader
        name="auth-refactor"
        spawnCount={3}
        lastActivity={new Date(Date.now() - 5 * 60 * 1000)}
        defaultOpen={true}
      >
        <div className="flex flex-col">
          {mockSpawns.slice(0, 2).map((spawn) => (
            <SessionRow
              key={spawn.spawn_id}
              spawn={spawn}
              onClick={() => console.log(`Clicked ${spawn.spawn_id}`)}
            />
          ))}
        </div>
      </WorkItemGroupHeader>
      <WorkItemGroupHeader
        name="api-redesign"
        spawnCount={1}
        lastActivity={new Date(Date.now() - 30 * 60 * 1000)}
        defaultOpen={false}
      >
        <div className="flex flex-col">
          <SessionRow
            spawn={{ ...mockSpawns[2], work_id: "api-redesign" }}
            onClick={() => console.log("Clicked")}
          />
        </div>
      </WorkItemGroupHeader>
    </div>
  ),
}

export const Loading: Story = {
  render: () => (
    <div className="flex flex-col">
      <WorkItemGroupHeaderSkeleton />
      <WorkItemGroupHeaderSkeleton />
    </div>
  ),
}
