// Barrel exports for the chat feature.

export { ChatPage } from "./ChatPage"
export type { ChatPageProps } from "./ChatPage"
export type { ChatContextValue, ChatSelection, ModelSelection } from "./ChatContext"
export { ChatContext, ChatProvider, useChat } from "./ChatContext"
export { chatManifest } from "./manifest"
export { ChatSidebar } from "./ChatSidebar"
export type { ChatSidebarProps } from "./ChatSidebar"
export { ChatThreadView } from "./ChatThreadView"
export type { ChatThreadViewProps } from "./ChatThreadView"
export { ChatBanner } from "./components/ChatBanner"
export type { ChatBannerProps, ChatUIState } from "./components/ChatBanner"
export { Composer } from "./components/Composer"
export type { ComposerProps } from "./components/Composer"
export { ModelPicker } from "./components/ModelPicker"
export type { ModelPickerProps } from "./components/ModelPicker"
export { ZeroStateGreeting } from "./components/ZeroStateGreeting"
export type { ZeroStateGreetingProps } from "./components/ZeroStateGreeting"
export { useModelCatalog } from "./hooks/use-model-catalog"
export type {
  ModelCatalog,
  CatalogModel,
  QuickPickModel,
  UseModelCatalogReturn,
} from "./hooks/use-model-catalog"
