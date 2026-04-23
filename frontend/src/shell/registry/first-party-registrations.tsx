import { chatManifest } from '@/features/chat/manifest'
import { sessionsManifest } from '@/features/sessions/manifest'
import type { ExtensionRegistry } from './ExtensionRegistry'

export function registerFirstPartyExtensions(registry: ExtensionRegistry): void {
  registry.register(sessionsManifest)
  registry.register(chatManifest)
}
