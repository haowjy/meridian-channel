import { Check, CaretDown } from "@phosphor-icons/react"
import { StatusDot } from "@/components/atoms"
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
} from "@/components/ui/command"
import { cn } from "@/lib/utils"
import type { SpawnStatus } from "@/types/spawn"

// FilterChip - individual toggle chip
export interface FilterChipProps {
  label: string
  isActive: boolean
  count?: number
  icon?: React.ReactNode
  onClick: () => void
  className?: string
}

export function FilterChip({
  label,
  isActive,
  count,
  icon,
  onClick,
  className,
}: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
        "transition-all duration-[var(--duration-fast)]",
        "border",
        isActive
          ? "bg-accent-fill/10 border-accent-fill text-accent-text"
          : "bg-transparent border-border text-muted-foreground hover:bg-muted/50",
        className
      )}
    >
      {icon}
      <span>{label}</span>
      {count !== undefined && (
        <span
          className={cn(
            "text-[10px] tabular-nums",
            isActive ? "text-accent-text/80" : "text-muted-foreground/60"
          )}
        >
          {count}
        </span>
      )}
    </button>
  )
}

// FilterBar - the full filter row
export interface FilterBarProps {
  statusFilter: SpawnStatus | 'all'
  onStatusFilterChange: (status: SpawnStatus | 'all') => void
  statusCounts?: Partial<Record<SpawnStatus | 'all', number>>
  workItemFilter?: string | null
  onWorkItemFilterChange?: (workId: string | null) => void
  availableWorkItems?: Array<{ work_id: string; name: string }>
  agentFilter?: string | null
  onAgentFilterChange?: (agent: string | null) => void
  availableAgents?: string[]
  className?: string
}

type StatusFilterOption = {
  value: SpawnStatus | 'all'
  label: string
  statuses: (SpawnStatus | 'all')[]  // Which statuses to match
}

const statusFilterOptions: StatusFilterOption[] = [
  { value: 'all', label: 'All', statuses: ['all'] },
  { value: 'running', label: 'Running', statuses: ['running'] },
  { value: 'queued', label: 'Queued', statuses: ['queued'] },
  { value: 'succeeded', label: 'Done', statuses: ['succeeded', 'cancelled', 'finalizing'] },
  { value: 'failed', label: 'Failed', statuses: ['failed'] },
]

export function FilterBar({
  statusFilter,
  onStatusFilterChange,
  statusCounts,
  workItemFilter,
  onWorkItemFilterChange,
  availableWorkItems,
  agentFilter,
  onAgentFilterChange,
  availableAgents,
  className,
}: FilterBarProps) {
  const selectedWorkItem = availableWorkItems?.find(
    (w) => w.work_id === workItemFilter
  )

  return (
    <div className={cn("flex items-center gap-2 flex-wrap", className)}>
      {/* Status filter chips */}
      <div className="flex items-center gap-1">
        {statusFilterOptions.map((option) => {
          // Get icon based on status
          let icon: React.ReactNode = null
          if (option.value !== 'all') {
            icon = <StatusDot status={option.value} size="sm" />
          }

          // Calculate count for this filter option
          const count = statusCounts?.[option.value]

          return (
            <FilterChip
              key={option.value}
              label={option.label}
              isActive={statusFilter === option.value}
              count={count}
              icon={icon}
              onClick={() => onStatusFilterChange(option.value)}
            />
          )
        })}
      </div>

      {/* Work item filter */}
      {availableWorkItems && onWorkItemFilterChange && (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(
                "h-7 px-2 text-xs gap-1",
                workItemFilter && "border-accent-fill text-accent-text"
              )}
            >
              <span className="max-w-[120px] truncate">
                {selectedWorkItem?.name ?? "Work item"}
              </span>
              <CaretDown size={12} />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[200px] p-0" align="start">
            <Command>
              <CommandInput placeholder="Search work items..." className="h-8" />
              <CommandList>
                <CommandEmpty>No work items found.</CommandEmpty>
                <CommandGroup>
                  <CommandItem
                    value=""
                    onSelect={() => onWorkItemFilterChange(null)}
                  >
                    <Check
                      size={14}
                      className={cn(
                        "mr-2",
                        !workItemFilter ? "opacity-100" : "opacity-0"
                      )}
                    />
                    All work items
                  </CommandItem>
                  {availableWorkItems.map((item) => (
                    <CommandItem
                      key={item.work_id}
                      value={item.name}
                      onSelect={() => onWorkItemFilterChange(item.work_id)}
                    >
                      <Check
                        size={14}
                        className={cn(
                          "mr-2",
                          workItemFilter === item.work_id
                            ? "opacity-100"
                            : "opacity-0"
                        )}
                      />
                      <span className="truncate">{item.name}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}

      {/* Agent filter */}
      {availableAgents && onAgentFilterChange && (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(
                "h-7 px-2 text-xs gap-1",
                agentFilter && "border-accent-fill text-accent-text"
              )}
            >
              <span className="max-w-[100px] truncate">
                {agentFilter ?? "Agent"}
              </span>
              <CaretDown size={12} />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[180px] p-0" align="start">
            <Command>
              <CommandInput placeholder="Search agents..." className="h-8" />
              <CommandList>
                <CommandEmpty>No agents found.</CommandEmpty>
                <CommandGroup>
                  <CommandItem
                    value=""
                    onSelect={() => onAgentFilterChange(null)}
                  >
                    <Check
                      size={14}
                      className={cn(
                        "mr-2",
                        !agentFilter ? "opacity-100" : "opacity-0"
                      )}
                    />
                    All agents
                  </CommandItem>
                  {availableAgents.map((agent) => (
                    <CommandItem
                      key={agent}
                      value={agent}
                      onSelect={() => onAgentFilterChange(agent)}
                    >
                      <Check
                        size={14}
                        className={cn(
                          "mr-2",
                          agentFilter === agent ? "opacity-100" : "opacity-0"
                        )}
                      />
                      <span className="truncate">{agent}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}
    </div>
  )
}
