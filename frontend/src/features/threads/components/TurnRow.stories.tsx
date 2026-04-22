import type { Meta, StoryObj } from "@storybook/react-vite"

import { STATUS_SCENARIO_TURNS, TURN_STATUS_ORDER } from "../stories"

import { TurnRow } from "./TurnRow"

const meta = {
  title: "Features/Threads/TurnRow",
  component: TurnRow,
  tags: ["autodocs"],
  args: {
    turn: STATUS_SCENARIO_TURNS.complete,
  },
  parameters: {
    layout: "padded",
  },
} satisfies Meta<typeof TurnRow>

export default meta
type Story = StoryObj<typeof meta>

export const Pending: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.pending,
  },
}

export const Streaming: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.streaming,
  },
}

export const WaitingSubagents: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.waiting_subagents,
  },
}

export const Complete: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.complete,
  },
}

export const Cancelled: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.cancelled,
  },
}

export const Error: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.error,
  },
}

export const CreditLimited: Story = {
  args: {
    turn: STATUS_SCENARIO_TURNS.credit_limited,
  },
}

export const AllStatuses: Story = {
  render: () => (
    <div className="max-w-3xl space-y-4">
      {TURN_STATUS_ORDER.map((status) => (
        <div key={status} className="space-y-2">
          <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{status}</p>
          <TurnRow turn={STATUS_SCENARIO_TURNS[status]} />
        </div>
      ))}
    </div>
  ),
}
