import { Badge } from "@/components/ui/badge"

interface StatusBarProps {
  connectionStatus: "connecting" | "connected" | "disconnected"
  spawnId: string | null
  harnessId: string | null
}

function getDotClassName(connectionStatus: StatusBarProps["connectionStatus"]): string {
  if (connectionStatus === "connected") {
    return "bg-success"
  }

  if (connectionStatus === "connecting") {
    return "bg-amber-500"
  }

  return "bg-destructive"
}

export function StatusBar({ connectionStatus, spawnId, harnessId }: StatusBarProps) {
  return (
    <footer className="border-t border-border bg-background/95 px-6 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className={`inline-block size-2 rounded-full ${getDotClassName(connectionStatus)}`} />
          <span className="font-mono">{connectionStatus}</span>
        </div>

        <div className="flex items-center gap-2">
          <span>active spawn</span>
          {spawnId ? (
            <>
              <Badge variant="outline" className="font-mono text-xs">
                {spawnId}
              </Badge>
              {harnessId ? (
                <Badge variant="secondary" className="font-mono text-xs uppercase">
                  {harnessId}
                </Badge>
              ) : null}
            </>
          ) : (
            <Badge variant="outline" className="font-mono text-xs">
              none
            </Badge>
          )}
        </div>
      </div>
    </footer>
  )
}
