import { ThemeProvider } from "@/components/theme-provider"
import { AppShell } from "@/shell"

function App() {
  return (
    <ThemeProvider>
      <AppShell />
    </ThemeProvider>
  )
}

export default App
