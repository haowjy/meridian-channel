import type { Meta, StoryObj } from "@storybook/react-vite"

import { SAMPLE_PARTIAL_REFERENCE, SAMPLE_REFERENCE } from "../stories/factories"

import { ReferenceBlock } from "./ReferenceBlock"

const meta = {
  title: "Features/Threads/Blocks/ReferenceBlock",
  component: ReferenceBlock,
  tags: ["autodocs"],
  args: {
    refId: SAMPLE_REFERENCE.refId,
    refType: SAMPLE_REFERENCE.refType,
    displayText: SAMPLE_REFERENCE.displayText,
    selectionStart: SAMPLE_REFERENCE.selectionStart,
    selectionEnd: SAMPLE_REFERENCE.selectionEnd,
  },
  parameters: {
    layout: "centered",
  },
} satisfies Meta<typeof ReferenceBlock>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const PartialReference: Story = {
  args: {
    refId: SAMPLE_PARTIAL_REFERENCE.refId,
    refType: SAMPLE_PARTIAL_REFERENCE.refType,
    displayText: SAMPLE_PARTIAL_REFERENCE.displayText,
    selectionStart: undefined,
    selectionEnd: undefined,
  },
}
