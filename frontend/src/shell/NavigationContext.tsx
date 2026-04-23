/**
 * Cross-mode navigation plumbing.
 *
 * The ModeViewport renders panels from the registry, so panels don't receive
 * callbacks directly from AppShell. This context is the seam: AppShell
 * provides it, any panel can consume it to request a mode switch.
 *
 * Navigation handoff pattern: `navigateToChat(spawnId)` both switches the
 * active mode AND records `pendingChatSpawnId`. ChatPage reads this on mount
 * (or on subsequent handoffs) via `useNavigation`, opens the spawn column,
 * then calls `clearPendingChatSpawnId` so the id isn't re-consumed. Keeping
 * this bit of state here — rather than threading an `initialSpawnId` prop
 * through the registry — lets ModeViewport stay generic.
 *
 * Outside AppShell (stories, isolated tests) the hook falls back to a
 * logging stub so components remain usable without a provider.
 */

import { createContext, useContext } from "react"

export interface NavigationContextValue {
  /** Switch to the chat mode, optionally focused on a specific spawn. */
  navigateToChat: (spawnId: string) => void
  /** Spawn ID requested by the last navigateToChat call. Cleared after consumption. */
  pendingChatSpawnId: string | null
  /** Clear the pending spawn ID after ChatPage has consumed it. */
  clearPendingChatSpawnId: () => void
}

export const NavigationContext = createContext<NavigationContextValue | null>(null)

export function useNavigation(): NavigationContextValue {
  const ctx = useContext(NavigationContext)
  if (!ctx) {
    return {
      navigateToChat: (spawnId) => {
        // eslint-disable-next-line no-console
        console.log("[navigation] navigateToChat:", spawnId)
      },
      pendingChatSpawnId: null,
      clearPendingChatSpawnId: () => {
        // no-op outside a provider
      },
    }
  }
  return ctx
}
