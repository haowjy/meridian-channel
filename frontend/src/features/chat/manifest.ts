import { ChatCircle } from "@phosphor-icons/react"

import type { ExtensionManifest } from "@/shell/registry/types"

import { ChatPage } from "./ChatPage"

export const chatManifest: ExtensionManifest = {
  id: "chat",
  name: "Chat",
  railItems: [
    {
      id: "chat",
      icon: ChatCircle,
      label: "Chat",
      order: 0,
    },
  ],
  panels: [{ id: "chat", component: ChatPage }],
  commands: [],
}
