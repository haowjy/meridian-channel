import type { Meta, StoryObj } from "@storybook/react-vite"
import { SessionRow, SessionRowSkeleton } from "./SessionRow"
import type { SpawnSummary, SpawnStatus } from "@/types/spawn"

const meta: Meta<typeof SessionRow> = {
  title: "Components/Molecules/SessionRow",
  component: SessionRow,
  parameters: {
    layout: "padded",
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl border rounded-md">
        <Story />
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof SessionRow>

// Mock spawn factory
function createSpawn(
  overrides: Partial<SpawnSummary> = {}
): SpawnSummary {
  const now = new Date()
  const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000)
  
  return {
    spawn_id: "p281",
    status: "running",
    agent: "coder",
    model: "claude-sonnet-4",
    harness: "claude",
    work_id: "auth-refactor",
    desc: "Implement authentication middleware",
    started_at: fiveMinutesAgo.toISOString(),
    finished_at: null,
    cost_usd: 0.42,
    ...overrides,
  }
}

// Basic stories for each status
export const Running: Story = {
  args: {
    spawn: createSpawn({ status: "running" }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

export const Queued: Story = {
  args: {
    spawn: createSpawn({ status: "queued", cost_usd: null }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

export const Succeeded: Story = {
  args: {
    spawn: createSpawn({
      status: "succeeded",
      finished_at: new Date().toISOString(),
      cost_usd: 1.23,
    }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

export const Failed: Story = {
  args: {
    spawn: createSpawn({
      status: "failed",
      finished_at: new Date().toISOString(),
      cost_usd: 0.15,
    }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

export const Cancelled: Story = {
  args: {
    spawn: createSpawn({
      status: "cancelled",
      finished_at: new Date().toISOString(),
      cost_usd: 0.08,
    }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

export const Finalizing: Story = {
  args: {
    spawn: createSpawn({ status: "finalizing" }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

// Selected state
export const Selected: Story = {
  args: {
    spawn: createSpawn({ status: "running" }),
    isSelected: true,
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

// Long description truncation
export const LongDescription: Story = {
  args: {
    spawn: createSpawn({
      desc: "This is a very long description that should be truncated with ellipsis because it exceeds the available space in the grid column",
    }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

// Null fields
export const NullFields: Story = {
  args: {
    spawn: createSpawn({
      agent: null,
      model: null,
      desc: null,
      cost_usd: null,
    }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
}

// All statuses comparison
const statuses: SpawnStatus[] = [
  "running",
  "queued",
  "succeeded",
  "failed",
  "cancelled",
  "finalizing",
]

export const AllStatuses: Story = {
  render: () => (
    <div className="flex flex-col">
      {statuses.map((status, i) => (
        <SessionRow
          key={status}
          spawn={createSpawn({
            spawn_id: `p${281 + i}`,
            status,
            finished_at: status !== "running" && status !== "queued" && status !== "finalizing"
              ? new Date().toISOString()
              : null,
          })}
          onClick={() => console.log(`Clicked ${status}`)}
          onContextAction={(action) => console.log(`${action} on ${status}`)}
        />
      ))}
    </div>
  ),
}

// Context menu demo (right-click to see)
export const ContextMenuDemo: Story = {
  args: {
    spawn: createSpawn({ status: "running" }),
    onClick: () => console.log("Clicked"),
    onContextAction: (action) => console.log("Context action:", action),
  },
  parameters: {
    docs: {
      description: {
        story: "Right-click on the row to see the context menu. Cancel is only available for running/queued spawns.",
      },
    },
  },
}

// Skeleton loading state
export const Loading: Story = {
  render: () => (
    <div className="flex flex-col gap-0">
      <SessionRowSkeleton />
      <SessionRowSkeleton />
      <SessionRowSkeleton />
    </div>
  ),
}
