import { useEffect, useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  ChatCircle,
  ListDashes,
  Lightning,
  Flask,
  FileText,
  GitBranch,
  MagnifyingGlass,
  Terminal,
  Bug,
  Wrench,
} from "@phosphor-icons/react"

import { CommandPalette } from "./CommandPalette"
import { registry } from "./registry"

const meta: Meta<typeof CommandPalette> = {
  title: "Shell/CommandPalette",
  component: CommandPalette,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <div className="flex h-screen items-center justify-center bg-background p-8 text-foreground">
        <div className="text-center text-sm text-muted-foreground">
          Press the palette — or see it open below.
        </div>
        <Story />
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof CommandPalette>

/** Base set of extensions used by most stories. */
function useRegisterBaseExtensions() {
  useEffect(() => {
    registry.register({
      id: "demo-sessions",
      name: "Sessions",
      railItems: [
        { id: "sessions", icon: ListDashes, label: "Sessions", order: 0 },
      ],
      panels: [],
      commands: [
        {
          id: "switch-to-sessions",
          label: "Go to Sessions",
          shortcut: "⌘1",
          category: "Navigation",
          execute: () => console.log("switch sessions"),
        },
        {
          id: "sessions.archive",
          label: "Archive current session",
          category: "Sessions",
          execute: () => console.log("archive"),
        },
      ],
    })

    registry.register({
      id: "demo-chat",
      name: "Chat",
      railItems: [{ id: "chat", icon: ChatCircle, label: "Chat", order: 1 }],
      panels: [],
      commands: [
        {
          id: "switch-to-chat",
          label: "Go to Chat",
          shortcut: "⌘2",
          category: "Navigation",
          execute: () => console.log("switch chat"),
        },
      ],
    })

    registry.register({
      id: "demo-actions",
      name: "Actions",
      railItems: [
        { id: "actions", icon: Lightning, label: "Actions", order: 2 },
      ],
      panels: [],
      commands: [
        {
          id: "switch-to-actions",
          label: "Go to Actions",
          shortcut: "⌘3",
          category: "Navigation",
          execute: () => console.log("switch actions"),
        },
      ],
    })

    return () => {
      registry.unregister("demo-sessions")
      registry.unregister("demo-chat")
      registry.unregister("demo-actions")
    }
  }, [])
}

/** Extended set with many commands across categories. */
function useRegisterManyExtensions() {
  useEffect(() => {
    registry.register({
      id: "demo-many",
      name: "Many",
      railItems: [
        { id: "search", icon: MagnifyingGlass, label: "Search", order: 10 },
        { id: "terminal", icon: Terminal, label: "Terminal", order: 11 },
        { id: "tests", icon: Flask, label: "Tests", order: 12 },
      ],
      panels: [],
      commands: [
        {
          id: "switch-to-search",
          label: "Go to Search",
          shortcut: "⌘4",
          category: "Navigation",
          execute: () => console.log("search"),
        },
        {
          id: "switch-to-terminal",
          label: "Go to Terminal",
          shortcut: "⌘5",
          category: "Navigation",
          execute: () => console.log("terminal"),
        },
        {
          id: "switch-to-tests",
          label: "Go to Tests",
          shortcut: "⌘6",
          category: "Navigation",
          execute: () => console.log("tests"),
        },
        {
          id: "git.commit",
          label: "Create commit…",
          shortcut: "⌘⇧G",
          category: "Git",
          execute: () => console.log("commit"),
        },
        {
          id: "git.push",
          label: "Push branch",
          category: "Git",
          execute: () => console.log("push"),
        },
        {
          id: "docs.new",
          label: "New documentation page",
          category: "Docs",
          execute: () => console.log("new doc"),
        },
        {
          id: "debug.attach",
          label: "Attach debugger",
          category: "Debug",
          execute: () => console.log("attach"),
        },
        {
          id: "tool.refactor",
          label: "Run refactor…",
          shortcut: "⌘⇧R",
          category: "Tools",
          execute: () => console.log("refactor"),
        },
        {
          id: "tool.format",
          label: "Format file",
          shortcut: "⌥⇧F",
          category: "Tools",
          execute: () => console.log("format"),
        },
      ],
    })
    // icons only exist so the registration is consistent with rail icons
    void FileText
    void GitBranch
    void Bug
    void Wrench
    return () => registry.unregister("demo-many")
  }, [])
}

function Harness({
  initialOpen = true,
  initialSearch,
}: {
  initialOpen?: boolean
  initialSearch?: string
}) {
  const [open, setOpen] = useState(initialOpen)
  const [search, setSearch] = useState(initialSearch ?? "")

  useEffect(() => {
    if (initialSearch !== undefined) setSearch(initialSearch)
  }, [initialSearch])

  return (
    <>
      <CommandPalette
        open={open}
        onOpenChange={setOpen}
        onSwitchMode={(id) => console.log("switch mode:", id)}
        onNewSession={() => console.log("new chat")}
        /* re-mount trick: key by search so CommandInput honours defaultValue */
        key={search}
      />
      {/* Controlled input fed into cmdk via defaultValue is awkward; instead we
          key the palette so stories can demo pre-filtered states cleanly. */}
      <HiddenSearchSetter search={search} />
      <HiddenOpener setOpen={setOpen} />
    </>
  )
}

function HiddenSearchSetter({ search }: { search: string }) {
  useEffect(() => {
    if (!search) return
    const id = requestAnimationFrame(() => {
      const el = document.querySelector<HTMLInputElement>(
        '[data-slot="command-input"]',
      )
      if (el) {
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          "value",
        )?.set
        setter?.call(el, search)
        el.dispatchEvent(new Event("input", { bubbles: true }))
      }
    })
    return () => cancelAnimationFrame(id)
  }, [search])
  return null
}

function HiddenOpener({ setOpen }: { setOpen: (v: boolean) => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [setOpen])
  return null
}

export const Default: Story = {
  render: () => {
    const Inner = () => {
      useRegisterBaseExtensions()
      return <Harness />
    }
    return <Inner />
  },
}

export const Filtered: Story = {
  render: () => {
    const Inner = () => {
      useRegisterBaseExtensions()
      return <Harness initialSearch="chat" />
    }
    return <Inner />
  },
}

export const Empty: Story = {
  render: () => {
    const Inner = () => {
      useRegisterBaseExtensions()
      return <Harness initialSearch="zzznothingmatches" />
    }
    return <Inner />
  },
}

export const ManyCommands: Story = {
  render: () => {
    const Inner = () => {
      useRegisterBaseExtensions()
      useRegisterManyExtensions()
      return <Harness />
    }
    return <Inner />
  },
}
