import { createContext, useContext, useMemo, type ReactNode } from "react"

import type { ActivityBlockData } from "./types"

type ActivityNesting = {
  depth: number
  renderNestedActivity: (activity: ActivityBlockData, depth: number) => ReactNode
}

const ActivityNestingContext = createContext<ActivityNesting | null>(null)

type ActivityNestingProviderProps = {
  depth: number
  renderNestedActivity: (activity: ActivityBlockData, depth: number) => ReactNode
  children: ReactNode
}

export function ActivityNestingProvider({
  depth,
  renderNestedActivity,
  children,
}: ActivityNestingProviderProps) {
  const value = useMemo(
    () => ({ depth, renderNestedActivity }),
    [depth, renderNestedActivity]
  )

  return (
    <ActivityNestingContext.Provider value={value}>
      {children}
    </ActivityNestingContext.Provider>
  )
}

export function useActivityNesting() {
  const ctx = useContext(ActivityNestingContext)
  if (!ctx) {
    throw new Error("useActivityNesting must be used within an ActivityBlock")
  }
  return ctx
}
