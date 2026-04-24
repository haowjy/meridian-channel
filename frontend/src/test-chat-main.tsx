import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { ThemeProvider } from "@/components/theme-provider"
import { TestChatPage } from "@/features/test-chat/TestChatPage"

import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <TestChatPage />
    </ThemeProvider>
  </StrictMode>,
)
