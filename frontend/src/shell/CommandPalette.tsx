import { useMemo } from "react"
import { Moon, Sun } from "lucide-react"
import { Plus } from "@phosphor-icons/react"

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { useTheme } from "@/components/theme-provider"
import type { CommandContribution, RailItemContribution } from "./registry"
import { useRegistry } from "./registry"

export interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSwitchMode: (modeId: string) => void
  onNewSession?: () => void
}

const DEFAULT_CATEGORY = "Commands"
const SWITCH_PREFIX = "switch-to-"

interface ResolvedCommand extends CommandContribution {
  category: string
  icon?: RailItemContribution["icon"]
}

/**
 * Shell-level command palette.
 *
 * Aggregates registry-contributed commands with shell built-ins (new chat,
 * toggle theme) and exposes fuzzy search through cmdk. Mode-switch commands
 * (id prefix `switch-to-`) are enriched with the rail icon of the matching
 * extension so they read consistently with the activity bar.
 *
 * Note: The project ships its own theme-provider with the same API shape as
 * next-themes, so we consume it directly instead of pulling in a second
 * theming library.
 */
export function CommandPalette({
  open,
  onOpenChange,
  onSwitchMode,
  onNewSession,
}: CommandPaletteProps) {
  const registry = useRegistry()
  const registryVersion = registry.getSnapshot()
  const { resolvedTheme, setTheme } = useTheme()

  const railIconById = useMemo(() => {
    const map = new Map<string, RailItemContribution["icon"]>()
    for (const item of registry.getRailItems()) {
      map.set(item.id, item.icon)
    }
    return map
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registryVersion])

  const grouped = useMemo(() => {
    const registryCommands = registry.getCommands()

    const builtins: ResolvedCommand[] = [
      {
        id: "toggle-theme",
        label:
          resolvedTheme === "dark"
            ? "Toggle Theme — Light"
            : "Toggle Theme — Dark",
        category: "Preferences",
        execute: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
      },
    ]

    if (onNewSession) {
      builtins.unshift({
        id: "new-chat",
        label: "New Chat",
        shortcut: "⌘N",
        category: "Actions",
        icon: Plus,
        execute: onNewSession,
      })
    }

    const resolved: ResolvedCommand[] = registryCommands.map((cmd) => {
      const category = cmd.category ?? DEFAULT_CATEGORY
      let icon: RailItemContribution["icon"] | undefined
      if (cmd.id.startsWith(SWITCH_PREFIX)) {
        const modeId = cmd.id.slice(SWITCH_PREFIX.length)
        icon = railIconById.get(modeId)
      }
      return { ...cmd, category, icon }
    })

    const all = [...resolved, ...builtins]
    const byCategory = new Map<string, ResolvedCommand[]>()
    for (const cmd of all) {
      const bucket = byCategory.get(cmd.category) ?? []
      bucket.push(cmd)
      byCategory.set(cmd.category, bucket)
    }
    // Stable category ordering: Navigation first if present, then alpha,
    // with Actions and Preferences pinned last.
    const pinnedLast = new Set(["Actions", "Preferences"])
    const categories = Array.from(byCategory.keys())
    categories.sort((a, b) => {
      const aLast = pinnedLast.has(a)
      const bLast = pinnedLast.has(b)
      if (aLast && !bLast) return 1
      if (!aLast && bLast) return -1
      return a.localeCompare(b)
    })
    return categories.map((cat) => ({
      category: cat,
      items: byCategory.get(cat) ?? [],
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registryVersion, railIconById, onNewSession, resolvedTheme, setTheme])

  const handleSelect = (cmd: ResolvedCommand) => {
    if (cmd.id.startsWith(SWITCH_PREFIX)) {
      const modeId = cmd.id.slice(SWITCH_PREFIX.length)
      onSwitchMode(modeId)
    } else {
      cmd.execute()
    }
    onOpenChange(false)
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command Palette"
      description="Search commands, switch modes, and trigger actions."
    >
      <CommandInput placeholder="Type a command..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        {grouped.map((group, idx) => (
          <div key={group.category}>
            {idx > 0 && <CommandSeparator />}
            <CommandGroup heading={group.category}>
              {group.items.map((cmd) => {
                const Icon = cmd.icon
                return (
                  <CommandItem
                    key={cmd.id}
                    value={`${cmd.category} ${cmd.label}`}
                    onSelect={() => handleSelect(cmd)}
                  >
                    {Icon ? (
                      <Icon weight="regular" />
                    ) : cmd.category === "Preferences" &&
                      cmd.id === "toggle-theme" ? (
                      resolvedTheme === "dark" ? (
                        <Sun />
                      ) : (
                        <Moon />
                      )
                    ) : null}
                    <span>{cmd.label}</span>
                    {cmd.shortcut && (
                      <CommandShortcut>{cmd.shortcut}</CommandShortcut>
                    )}
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </div>
        ))}
      </CommandList>
    </CommandDialog>
  )
}
