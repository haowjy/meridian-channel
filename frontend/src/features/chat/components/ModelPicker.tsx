/**
 * ModelPicker — searchable model selector using cmdk + Popover.
 *
 * Shows a trigger button with the current selection (harness · alias),
 * and opens a popover with search-filterable quick picks and per-harness
 * groups (collapsed by default).
 */

import { useCallback, useState } from "react"
import { CaretUpDown, Check, Lightning } from "@phosphor-icons/react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import type { ModelSelection } from "../ChatContext"
import type { ModelCatalog, CatalogModel } from "../hooks/use-model-catalog"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ModelPickerProps {
  value: ModelSelection | null
  onChange: (selection: ModelSelection) => void
  catalog: ModelCatalog
  disabled?: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTriggerLabel(value: ModelSelection | null): string {
  if (!value) return "Select model…"
  return `${value.harness} · ${value.displayName}`
}

function costBadge(costTier: string | null): string | null {
  if (!costTier) return null
  // Normalize common tiers to short labels
  switch (costTier.toLowerCase()) {
    case "free":
      return "free"
    case "budget":
      return "$"
    case "standard":
      return "$$"
    case "premium":
      return "$$$"
    case "ultra":
      return "$$$$"
    default:
      return costTier
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ModelPicker({
  value,
  onChange,
  catalog,
  disabled = false,
}: ModelPickerProps) {
  const [open, setOpen] = useState(false)
  const [searchValue, setSearchValue] = useState("")

  // Force-expand all harness groups while the user is searching so that
  // matching models inside collapsed groups are visible.
  const forceExpandAll = searchValue.length > 0

  const handleSelect = useCallback(
    (modelId: string, harness: string, displayName: string) => {
      onChange({ modelId, harness, displayName })
      setOpen(false)
      setSearchValue("")
    },
    [onChange],
  )

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setSearchValue("")
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          className={cn(
            "h-7 gap-1.5 rounded-md border-border/60 px-2.5 text-xs font-medium",
            "bg-transparent text-muted-foreground hover:text-foreground",
            "transition-colors",
            value && "text-foreground",
          )}
          aria-label="Select model"
        >
          <Lightning className="size-3 text-accent-fill" weight="fill" />
          <span className="max-w-[180px] truncate">
            {formatTriggerLabel(value)}
          </span>
          <CaretUpDown className="size-3 opacity-50" />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-72 p-0"
        align="start"
        sideOffset={6}
      >
        <Command>
          <CommandInput
            placeholder="Search models…"
            value={searchValue}
            onValueChange={setSearchValue}
          />
          <CommandList className="max-h-[320px]">
            <CommandEmpty>No models found.</CommandEmpty>

            {/* Quick Pick section */}
            {catalog.quickPick.length > 0 && (
              <CommandGroup heading="Quick pick">
                {catalog.quickPick.map((pick) => {
                  const isSelected = value?.modelId === pick.modelId
                  const cost = costBadge(pick.costTier)

                  return (
                    <CommandItem
                      key={`qp-${pick.displayName}-${pick.modelId}`}
                      value={`${pick.displayName} ${pick.modelId} ${pick.harness}`}
                      onSelect={() =>
                        handleSelect(pick.modelId, pick.harness, pick.displayName)
                      }
                      className="flex items-center gap-2"
                    >
                      <Check
                        className={cn(
                          "size-3.5 shrink-0",
                          isSelected ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <div className="flex min-w-0 flex-1 items-center gap-2">
                        <span className="truncate font-medium">
                          {pick.displayName}
                        </span>
                        <span className="shrink-0 text-[10px] text-muted-foreground">
                          {pick.harness}
                        </span>
                      </div>
                      {cost && (
                        <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                          {cost}
                        </span>
                      )}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            )}

            {/* Per-harness sections (collapsible) */}
            {Array.from(catalog.byHarness.entries()).map(
              ([harness, models]) => (
                <HarnessGroup
                  key={harness}
                  harness={harness}
                  models={models}
                  selectedModelId={value?.modelId ?? null}
                  onSelect={handleSelect}
                  showSeparator={catalog.quickPick.length > 0}
                  forceOpen={forceExpandAll}
                />
              ),
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

// ---------------------------------------------------------------------------
// HarnessGroup — collapsible per-harness section
// ---------------------------------------------------------------------------

interface HarnessGroupProps {
  harness: string
  models: CatalogModel[]
  selectedModelId: string | null
  onSelect: (modelId: string, harness: string, displayName: string) => void
  showSeparator: boolean
  /** When true the group is forced open (e.g. during search). */
  forceOpen?: boolean
}

function HarnessGroup({
  harness,
  models,
  selectedModelId,
  onSelect,
  showSeparator,
  forceOpen = false,
}: HarnessGroupProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      {showSeparator && <CommandSeparator />}
      <Collapsible open={forceOpen || isOpen} onOpenChange={setIsOpen}>
        <CommandGroup>
          <CollapsibleTrigger className="flex w-full items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
            <CaretUpDown className="size-3" />
            <span className="uppercase tracking-wider">{harness}</span>
            <span className="ml-auto text-[10px] opacity-60">
              {models.length}
            </span>
          </CollapsibleTrigger>
          <CollapsibleContent>
            {models.map((model) => {
              const isSelected = selectedModelId === model.modelId
              const cost = costBadge(model.costTier)

              return (
                <CommandItem
                  key={`${harness}-${model.modelId}`}
                  value={`${model.displayName} ${model.modelId} ${harness} ${model.aliases.join(" ")}`}
                  onSelect={() =>
                    onSelect(model.modelId, model.harness, model.displayName)
                  }
                  className="flex items-center gap-2 pl-6"
                >
                  <Check
                    className={cn(
                      "size-3.5 shrink-0",
                      isSelected ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-sm">
                      {model.displayName}
                    </span>
                    {model.aliases.length > 0 && (
                      <span className="truncate text-[10px] text-muted-foreground">
                        {model.aliases.join(", ")}
                      </span>
                    )}
                  </div>
                  {cost && (
                    <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {cost}
                    </span>
                  )}
                </CommandItem>
              )
            })}
          </CollapsibleContent>
        </CommandGroup>
      </Collapsible>
    </>
  )
}
