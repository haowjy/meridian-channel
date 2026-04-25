import { chatManifest } from '@/features/chat/manifest'
import type { ExtensionRegistry } from './ExtensionRegistry'

export function registerFirstPartyExtensions(registry: ExtensionRegistry): void {
  registry.register(chatManifest)
}
