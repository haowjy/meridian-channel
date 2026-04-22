import type { Meta, StoryObj } from "@storybook/react-vite"

import { SAMPLE_IMAGE_URL } from "../stories/factories"

import { ImageBlock } from "./ImageBlock"

const meta = {
  title: "Features/Threads/Blocks/ImageBlock",
  component: ImageBlock,
  tags: ["autodocs"],
  args: {
    url: SAMPLE_IMAGE_URL,
    altText: "Upload preview for chapter scene notes",
  },
  parameters: {
    layout: "centered",
  },
  render: (args) => (
    <div className="max-w-md">
      <ImageBlock {...args} />
    </div>
  ),
} satisfies Meta<typeof ImageBlock>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const WithCaption: Story = {
  args: {
    caption: "Reference image uploaded with the prompt.",
  },
}
