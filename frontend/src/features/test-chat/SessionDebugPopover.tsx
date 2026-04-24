import { useCallback, useState } from "react"
import { Check, Copy } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
} from "@/components/ui/popover"
import type { ConnectionCapabilities, WsState } from "@/lib/ws"

import type { TestChatSessionInfo } from "./session-api"

interface SessionDebugPopoverProps {
  session: TestChatSessionInfo
  connectionState: WsState
  capabilities: ConnectionCapabilities | null
}

interface CopyValueProps {
  label: string
  value: string
}

function CopyValue({ label, value }: CopyValueProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }, [value])

  return (
    <div className="grid gap-1">
      <div className="text-[11px] font-medium uppercase text-muted-foreground">
        {label}
      </div>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all rounded bg-muted px-2 py-1 font-mono text-xs">
          {value}
        </code>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={handleCopy}
          aria-label={`Copy ${label}`}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </Button>
      </div>
    </div>
  )
}

export function SessionDebugPopover({
  session,
  connectionState,
  capabilities,
}: SessionDebugPopoverProps) {
  return (
    <PopoverContent align="end" className="w-[360px] space-y-4">
      <PopoverHeader>
        <PopoverTitle>Session</PopoverTitle>
        <PopoverDescription>
          Test chat metadata for the active spawn.
        </PopoverDescription>
      </PopoverHeader>

      <div className="grid gap-3">
        <CopyValue label="Spawn ID" value={session.spawn_id} />
        <CopyValue label="Chat ID" value={session.chat_id} />
        <CopyValue label="Session log" value={session.session_log_path} />
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs">
        <div>
          <div className="text-[11px] font-medium uppercase text-muted-foreground">
            WebSocket
          </div>
          <div className="font-mono">{connectionState}</div>
        </div>
        <div>
          <div className="text-[11px] font-medium uppercase text-muted-foreground">
            Capabilities
          </div>
          <div className="font-mono">
            {capabilities
              ? [
                  capabilities.supportsSteer ? "steer" : null,
                  capabilities.supportsInterrupt ? "interrupt" : null,
                  capabilities.supportsCancel ? "cancel" : null,
                ]
                  .filter(Boolean)
                  .join(", ") || "none"
              : "unknown"}
          </div>
        </div>
      </div>
    </PopoverContent>
  )
}
