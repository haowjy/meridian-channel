import type { Meta, StoryObj } from "@storybook/react-vite"

import { TooltipProvider } from "@/components/ui/tooltip"

import { ChatProvider } from "./ChatContext"
import { ThreadColumn } from "./ThreadColumn"

/**
 * Stories pin `detailsOverride` so `fetchSpawns` never hits the network.
 * `useThreadStreaming` still opens a websocket — in Storybook that fails
 * silently and the column renders in its idle empty state, which is
 * representative of the real first-paint experience before any frames
 * arrive from the spawn.
 */

const meta: Meta<typeof ThreadColumn> = {
  title: "Features/Chat/ThreadColumn",
  component: ThreadColumn,
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story) => (
      <TooltipProvider>
        <ChatProvider>
          <div className="flex h-[720px] gap-3 bg-muted/20 p-4">
            <Story />
          </div>
        </ChatProvider>
      </TooltipProvider>
    ),
  ],
  args: {
    spawnId: "p1022",
    isFocused: true,
    onClose: () => {
      // eslint-disable-next-line no-console
      console.log("[story] close column")
    },
    onFocus: () => {
      // eslint-disable-next-line no-console
      console.log("[story] focus column")
    },
    detailsOverride: {
      status: "running",
      agent: "frontend-coder",
      model: "opus-4-7",
      harness: "claude",
    },
  },
  render: (args) => (
    <div className="flex h-full w-[520px]">
      <ThreadColumn {...args} />
    </div>
  ),
}

export default meta
type Story = StoryObj<typeof ThreadColumn>

export const Focused: Story = {}

export const Unfocused: Story = {
  args: {
    isFocused: false,
  },
}

export const QueuedSpawn: Story = {
  args: {
    detailsOverride: {
      status: "queued",
      agent: "reviewer",
      model: "sonnet-4-6",
      harness: "claude",
    },
  },
}

export const TerminalSucceeded: Story = {
  args: {
    detailsOverride: {
      status: "succeeded",
      agent: "planner",
      model: "opus-4-7",
      harness: "claude",
    },
  },
}

export const TerminalFailed: Story = {
  args: {
    detailsOverride: {
      status: "failed",
      agent: "verifier",
      model: null,
      harness: "codex",
    },
  },
}

export const TwoColumnsSideBySide: Story = {
  render: () => (
    <>
      <div className="flex h-full w-[440px]">
        <ThreadColumn
          spawnId="p1022"
          isFocused
          onClose={() => undefined}
          onFocus={() => undefined}
          detailsOverride={{
            status: "running",
            agent: "frontend-coder",
            model: "opus-4-7",
            harness: "claude",
          }}
        />
      </div>
      <div className="flex h-full w-[440px]">
        <ThreadColumn
          spawnId="p1025"
          isFocused={false}
          onClose={() => undefined}
          onFocus={() => undefined}
          detailsOverride={{
            status: "queued",
            agent: "reviewer",
            model: "sonnet-4-6",
            harness: "claude",
          }}
        />
      </div>
    </>
  ),
}
