import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"
import { ModeIcon } from "./ModeIcon"
import {
  Chat,
  List,
  Files,
  Gear,
  Bell,
  Lightning,
  Cube,
  Terminal,
} from "@phosphor-icons/react"

const meta: Meta<typeof ModeIcon> = {
  title: "Components/Molecules/ModeIcon",
  component: ModeIcon,
  parameters: {
    layout: "centered",
  },
  decorators: [
    (Story) => (
      <div className="bg-sidebar p-2 rounded-md">
        <Story />
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof ModeIcon>

export const Active: Story = {
  args: {
    icon: Chat,
    label: "Chat",
    isActive: true,
    onClick: () => console.log("Clicked"),
  },
}

export const Inactive: Story = {
  args: {
    icon: Chat,
    label: "Chat",
    isActive: false,
    onClick: () => console.log("Clicked"),
  },
}

export const WithBadge: Story = {
  args: {
    icon: Bell,
    label: "Notifications",
    isActive: false,
    badge: 5,
    onClick: () => console.log("Clicked"),
  },
}

export const WithLargeBadge: Story = {
  args: {
    icon: Bell,
    label: "Notifications",
    isActive: false,
    badge: 150,
    onClick: () => console.log("Clicked"),
  },
}

// Interactive toggle demo
function ToggleDemo() {
  const [active, setActive] = useState(false)

  return (
    <ModeIcon
      icon={Chat}
      label="Chat"
      isActive={active}
      onClick={() => setActive(!active)}
    />
  )
}

export const Interactive: Story = {
  render: () => <ToggleDemo />,
}

// Activity bar simulation with multiple icons
function ActivityBarDemo() {
  const [activeMode, setActiveMode] = useState("sessions")

  const modes = [
    { id: "sessions", icon: List, label: "Sessions" },
    { id: "chat", icon: Chat, label: "Chat" },
    { id: "files", icon: Files, label: "Files" },
    { id: "terminal", icon: Terminal, label: "Terminal" },
  ]

  return (
    <div className="flex flex-col gap-1 bg-sidebar p-1 rounded-md">
      {modes.map((mode) => (
        <ModeIcon
          key={mode.id}
          icon={mode.icon}
          label={mode.label}
          isActive={activeMode === mode.id}
          onClick={() => setActiveMode(mode.id)}
        />
      ))}
      <div className="flex-1" />
      <ModeIcon
        icon={Bell}
        label="Notifications"
        isActive={false}
        badge={3}
        onClick={() => console.log("Notifications")}
      />
      <ModeIcon
        icon={Gear}
        label="Settings"
        isActive={activeMode === "settings"}
        onClick={() => setActiveMode("settings")}
      />
    </div>
  )
}

export const ActivityBar: Story = {
  render: () => <ActivityBarDemo />,
  decorators: [
    (Story) => (
      <div className="h-[400px]">
        <Story />
      </div>
    ),
  ],
}

// Various Phosphor icons
export const IconVariants: Story = {
  render: () => (
    <div className="flex flex-col gap-1 bg-sidebar p-1 rounded-md">
      <ModeIcon icon={List} label="List" isActive={true} onClick={() => {}} />
      <ModeIcon icon={Chat} label="Chat" isActive={false} onClick={() => {}} />
      <ModeIcon icon={Files} label="Files" isActive={false} onClick={() => {}} />
      <ModeIcon icon={Terminal} label="Terminal" isActive={false} onClick={() => {}} />
      <ModeIcon icon={Lightning} label="Quick Actions" isActive={false} onClick={() => {}} />
      <ModeIcon icon={Cube} label="Workbench" isActive={false} onClick={() => {}} />
    </div>
  ),
}
