import type { Meta, StoryObj } from "@storybook/react-vite"

import { TooltipProvider } from "@/components/ui/tooltip"

import { SpawnHeader } from "./SpawnHeader"

const meta: Meta<typeof SpawnHeader> = {
  title: "Features/Chat/SpawnHeader",
  component: SpawnHeader,
  parameters: {
    layout: "padded",
  },
  decorators: [
    (Story) => (
      <TooltipProvider>
        <div className="w-[640px] rounded-md border border-border bg-background">
          <Story />
        </div>
      </TooltipProvider>
    ),
  ],
  args: {
    spawnId: "p1022",
    agent: "frontend-coder",
    model: "opus-4-7",
    harness: "claude",
    status: "running",
    isStreaming: false,
    onInterrupt: () => {
      // eslint-disable-next-line no-console
      console.log("[story] interrupt")
    },
    onCancel: () => {
      // eslint-disable-next-line no-console
      console.log("[story] cancel")
    },
    onClose: () => {
      // eslint-disable-next-line no-console
      console.log("[story] close")
    },
  },
}

export default meta
type Story = StoryObj<typeof SpawnHeader>

export const IdleRunning: Story = {}

export const Streaming: Story = {
  args: {
    isStreaming: true,
  },
}

export const Queued: Story = {
  args: {
    status: "queued",
    isStreaming: false,
    spawnId: "p1023",
  },
}

export const Finalizing: Story = {
  args: {
    status: "finalizing",
    isStreaming: false,
  },
}

export const Succeeded: Story = {
  args: {
    status: "succeeded",
    isStreaming: false,
    agent: "reviewer",
    model: "sonnet-4-6",
  },
}

export const Failed: Story = {
  args: {
    status: "failed",
    isStreaming: false,
    agent: "verifier",
    model: null,
  },
}

export const NoAgent: Story = {
  args: {
    agent: null,
    model: "gpt-5.3",
    harness: "codex",
  },
}

export const LongAgentName: Story = {
  args: {
    agent: "meridian-default-orchestrator",
    model: "claude-opus-4-7",
  },
}

export const WithChatContext: Story = {
  args: {
    chatId: "c001",
    chatTitle: "Auth middleware",
  },
}

export const WithChatContextNoTitle: Story = {
  args: {
    chatId: "c001abc",
  },
}
