import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  SAMPLE_PARTIAL_REFERENCE,
  SAMPLE_REFERENCE,
  imageBlock,
  referenceBlock,
  textBlock,
  toolResultBlock,
  userTurn,
} from "../stories/factories"

import { UserBubble } from "./UserBubble"

const meta = {
  title: "Features/Threads/UserBubble",
  component: UserBubble,
  tags: ["autodocs"],
  parameters: {
    layout: "padded",
  },
  args: {
    turn: userTurn([textBlock("text-1", "Could you revise this passage for pacing?", 1)]),
  },
} satisfies Meta<typeof UserBubble>

export default meta
type Story = StoryObj<typeof meta>

export const TextOnly: Story = {}

export const ImageOnly: Story = {
  args: {
    turn: userTurn([
      imageBlock("image-1", {
        sequence: 1,
        caption: "Include this mood board image in the scene revision.",
      }),
    ]),
  },
}

export const ReferenceOnly: Story = {
  args: {
    turn: userTurn([
      referenceBlock("reference-1", {
        sequence: 1,
        refId: SAMPLE_REFERENCE.refId,
        refType: SAMPLE_REFERENCE.refType,
        displayText: SAMPLE_REFERENCE.displayText,
        selectionStart: SAMPLE_REFERENCE.selectionStart,
        selectionEnd: SAMPLE_REFERENCE.selectionEnd,
      }),
    ]),
  },
}

export const MixedBlocks: Story = {
  args: {
    turn: userTurn([
      textBlock("mixed-text-1", "Use this image and excerpt to rewrite the opening paragraph.", 1),
      imageBlock("mixed-image-1", {
        sequence: 2,
        caption: "Atmosphere reference",
      }),
      referenceBlock("mixed-reference-1", {
        sequence: 3,
        refId: SAMPLE_PARTIAL_REFERENCE.refId,
        refType: SAMPLE_PARTIAL_REFERENCE.refType,
        displayText: SAMPLE_PARTIAL_REFERENCE.displayText,
        partial: true,
      }),
      toolResultBlock("mixed-tool-result-1", 4),
      textBlock("mixed-text-2", "Keep the same tone as the excerpt.", 5),
    ]),
  },
}
