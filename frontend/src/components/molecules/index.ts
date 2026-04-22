// Session management
export { SessionRow, SessionRowSkeleton, type SessionRowProps } from "./SessionRow"
export {
  WorkItemGroupHeader,
  WorkItemGroupHeaderSkeleton,
  type WorkItemGroupHeaderProps,
} from "./WorkItemGroupHeader"

// Filtering
export {
  FilterChip,
  FilterBar,
  type FilterChipProps,
  type FilterBarProps,
} from "./FilterBar"

// Dialog
export { NewSessionDialog, type NewSessionDialogProps } from "./NewSessionDialog"

// Navigation
export { ModeIcon, type ModeIconProps } from "./ModeIcon"

// Re-export types for convenience
export type { SpawnSummary, WorkItemSummary, SpawnStatus } from "@/types/spawn"
