import { ChatCircle } from "@phosphor-icons/react"

import type { ExtensionManifest } from "@/shell/registry/types"

import { ChatPage } from "./ChatPage"

/**
 * First-party manifest for Chat mode.
 *
 * Mode switching is owned by the shell, so the `switch-to-chat` command is
 * a no-op placeholder the shell overrides at registration time. Rail
 * ordering places Chat just below Sessions (order 0) so the two
 * session-centric modes cluster at the top of the activity bar.
 */
export const chatManifest: ExtensionManifest = {
  id: "chat",
  name: "Chat",
  railItems: [
    {
      id: "chat",
      icon: ChatCircle,
      label: "Chat",
      order: 1,
    },
  ],
  panels: [{ id: "chat", component: ChatPage }],
  commands: [
    {
      id: "switch-to-chat",
      label: "Switch to Chat",
      execute: () => {
        // Shell handles mode switching.
      },
    },
  ],
}
