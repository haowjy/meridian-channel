import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"
import { NewSessionDialog } from "./NewSessionDialog"
import { Button } from "@/components/ui/button"

const meta: Meta<typeof NewSessionDialog> = {
  title: "Components/Molecules/NewSessionDialog",
  component: NewSessionDialog,
  parameters: {
    layout: "centered",
  },
}

export default meta
type Story = StoryObj<typeof NewSessionDialog>

const defaultAgents = [
  "coder",
  "reviewer",
  "smoke-tester",
  "verifier",
  "frontend-coder",
  "refactor-coder",
  "investigator",
]

const defaultModels = [
  "claude-sonnet-4",
  "claude-opus-4",
  "gpt-4o",
  "codex",
]

const defaultWorkItems = [
  { work_id: "auth-refactor", name: "auth-refactor" },
  { work_id: "api-redesign", name: "api-redesign" },
  { work_id: "ui-polish", name: "ui-polish" },
]

// Wrapper to show dialog with trigger button
function DialogDemo({
  availableAgents = defaultAgents,
  availableModels = defaultModels,
  availableWorkItems = defaultWorkItems,
  defaultHarness = "claude",
  isSubmitting = false,
}: {
  availableAgents?: string[]
  availableModels?: string[]
  availableWorkItems?: Array<{ work_id: string; name: string }>
  defaultHarness?: string
  isSubmitting?: boolean
}) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <NewSessionDialog
        open={open}
        onOpenChange={setOpen}
        onSubmit={(request) => {
          console.log("Submit:", request)
          setOpen(false)
        }}
        availableAgents={availableAgents}
        availableModels={availableModels}
        availableWorkItems={availableWorkItems}
        defaultHarness={defaultHarness}
        isSubmitting={isSubmitting}
      />
    </>
  )
}

export const Default: Story = {
  render: () => <DialogDemo />,
}

export const OpenByDefault: Story = {
  args: {
    open: true,
    onOpenChange: () => console.log("Open change"),
    onSubmit: (request) => console.log("Submit:", request),
    availableAgents: defaultAgents,
    availableModels: defaultModels,
    availableWorkItems: defaultWorkItems,
    defaultHarness: "claude",
  },
}

export const NoWorkItems: Story = {
  render: () => (
    <DialogDemo availableWorkItems={[]} />
  ),
}

export const MinimalOptions: Story = {
  render: () => (
    <DialogDemo
      availableAgents={[]}
      availableModels={[]}
      availableWorkItems={[]}
    />
  ),
}

export const CodexHarness: Story = {
  render: () => (
    <DialogDemo defaultHarness="codex" />
  ),
}

// Interactive story that shows the resolved command updating
function CommandPreviewDemo() {
  const [open, setOpen] = useState(true)

  return (
    <NewSessionDialog
      open={open}
      onOpenChange={setOpen}
      onSubmit={(request) => {
        console.log("Submitted:", request)
        alert(JSON.stringify(request, null, 2))
      }}
      availableAgents={defaultAgents}
      availableModels={defaultModels}
      availableWorkItems={defaultWorkItems}
      defaultHarness="claude"
    />
  )
}

export const CommandPreview: Story = {
  render: () => <CommandPreviewDemo />,
  parameters: {
    docs: {
      description: {
        story: "Select different options to see the CLI command update in real-time.",
      },
    },
  },
}

// Submitting state
function SubmittingDemo() {
  const [open, setOpen] = useState(true)

  return (
    <NewSessionDialog
      open={open}
      onOpenChange={setOpen}
      onSubmit={() => {}}
      availableAgents={defaultAgents}
      availableModels={defaultModels}
      availableWorkItems={defaultWorkItems}
      isSubmitting={true}
    />
  )
}

export const Submitting: Story = {
  render: () => <SubmittingDemo />,
}

// Pre-filled with specific selections
function PrefilledDemo() {
  const [open, setOpen] = useState(true)

  return (
    <>
      <NewSessionDialog
        open={open}
        onOpenChange={setOpen}
        onSubmit={(request) => {
          console.log("Submit:", request)
          setOpen(false)
        }}
        availableAgents={defaultAgents}
        availableModels={defaultModels}
        availableWorkItems={defaultWorkItems}
        defaultHarness="claude"
      />
    </>
  )
}

export const Prefilled: Story = {
  render: () => <PrefilledDemo />,
  parameters: {
    docs: {
      description: {
        story: "Dialog opens with form ready for input. Type a prompt and press ⌘+Enter to submit.",
      },
    },
  },
}
