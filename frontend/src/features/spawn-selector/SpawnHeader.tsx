import { Badge } from "@/components/ui/badge"
import { CapabilityBadge } from "@/features/threads/composer/CapabilityBadge"
import type { ConnectionCapabilities } from "@/lib/ws"

interface SpawnHeaderProps {
  spawnId: string
  harnessId: string | null
  capabilities: ConnectionCapabilities | null
  connectionStatus: "connecting" | "connected" | "disconnected"
}

function getConnectionTone(connectionStatus: SpawnHeaderProps["connectionStatus"]): string {
  if (connectionStatus === "connected") {
    return "bg-success"
  }

  if (connectionStatus === "connecting") {
    return "bg-amber-500"
  }

  return "bg-destructive"
}

export function SpawnHeader({
  spawnId,
  harnessId,
  capabilities,
  connectionStatus,
}: SpawnHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <Badge variant="outline" className="font-mono text-xs">
          {spawnId}
        </Badge>
        <Badge variant="secondary" className="font-mono text-xs uppercase">
          {harnessId ?? "unknown"}
        </Badge>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <Badge variant="outline" className="font-mono text-xs">
          <span className={`mr-1.5 inline-block size-1.5 rounded-full ${getConnectionTone(connectionStatus)}`} />
          {connectionStatus}
        </Badge>
        <CapabilityBadge capabilities={capabilities} />
      </div>
    </div>
  )
}
