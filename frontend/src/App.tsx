import { useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ThreadView } from "@/features/threads/components/ThreadView"
import { StreamingIndicator } from "@/features/threads/components/StreamingIndicator"
import { useThreadStreaming } from "@/hooks/use-thread-streaming"

function App() {
  const [spawnIdInput, setSpawnIdInput] = useState("")
  const [spawnId, setSpawnId] = useState<string | null>(null)

  const { state, capabilities, cancel } = useThreadStreaming(spawnId)

  const canConnect = useMemo(() => spawnIdInput.trim().length > 0, [spawnIdInput])

  function handleConnect(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const nextSpawnId = spawnIdInput.trim()
    if (!nextSpawnId) {
      return
    }

    setSpawnId(nextSpawnId)
    setSpawnIdInput(nextSpawnId)
  }

  function handleDisconnect() {
    setSpawnId(null)
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-3">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm tracking-tight text-accent-text font-semibold">
              meridian
            </span>
            <Badge variant="secondary" className="text-xs font-mono">
              app
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            {spawnId ? (
              <Badge variant="outline" className="font-mono text-xs">
                spawn: {spawnId}
              </Badge>
            ) : (
              <Badge variant="outline" className="font-mono text-xs">
                no spawns
              </Badge>
            )}
            {state.isCancelled ? (
              <Badge variant="destructive" className="font-mono text-xs">
                cancelled
              </Badge>
            ) : null}
          </div>
        </div>
      </header>

      <main className="px-6 py-6">
        <form
          onSubmit={handleConnect}
          className="mx-auto mb-4 flex w-full max-w-5xl items-center gap-2"
        >
          <Input
            placeholder="Enter spawn ID"
            value={spawnIdInput}
            onChange={(event) => setSpawnIdInput(event.target.value)}
          />
          <Button type="submit" size="sm" disabled={!canConnect}>
            Connect
          </Button>
          {spawnId ? (
            <Button type="button" size="sm" variant="outline" onClick={handleDisconnect}>
              Disconnect
            </Button>
          ) : null}
          {spawnId ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={cancel}
              disabled={!state.isStreaming}
            >
              Cancel Run
            </Button>
          ) : null}
        </form>

        {!spawnId ? (
          <div className="mx-auto flex w-full max-w-lg items-center justify-center py-20">
            <Card className="w-full">
              <CardHeader>
                <CardTitle className="font-mono text-lg">Spawn Workspace</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground leading-relaxed">
                  No active spawns. Create one via the API or connect to an existing spawn
                  to see streaming AG-UI events here.
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled>
                    Connect to Spawn
                  </Button>
                  <Button size="sm" disabled>
                    New Spawn
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="mx-auto flex h-[calc(100vh-11rem)] w-full max-w-5xl flex-col gap-3">
            {capabilities ? (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="secondary" className="font-mono">
                  mid-turn: {capabilities.midTurnInjection}
                </Badge>
                <Badge variant="outline" className="font-mono">
                  interrupt: {String(capabilities.supportsInterrupt)}
                </Badge>
                <Badge variant="outline" className="font-mono">
                  cancel: {String(capabilities.supportsCancel)}
                </Badge>
              </div>
            ) : null}

            <div className="min-h-0 flex-1">
              <ThreadView items={state.items} error={state.error} />
            </div>
            {state.isStreaming ? <StreamingIndicator /> : null}
          </div>
        )}
      </main>
    </div>
  )
}

export default App
