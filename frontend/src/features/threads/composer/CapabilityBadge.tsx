import { Mail, Send, Zap } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ConnectionCapabilities } from "@/lib/ws"

interface CapabilityBadgeProps {
  capabilities: ConnectionCapabilities | null
}

function getCapabilityMeta(capabilities: ConnectionCapabilities | null): {
  label: string
  tooltip: string
  Icon: typeof Mail
} {
  if (!capabilities) {
    return {
      label: "Detecting",
      tooltip: "Waiting for harness capabilities from the active spawn.",
      Icon: Send,
    }
  }

  if (capabilities.midTurnInjection === "queue") {
    return {
      label: "Queue",
      tooltip: "Messages are queued and delivered at the next model turn.",
      Icon: Mail,
    }
  }

  if (capabilities.midTurnInjection === "interrupt_restart") {
    return {
      label: "Steer",
      tooltip: "Messages can steer the in-flight turn while the model is running.",
      Icon: Zap,
    }
  }

  return {
    label: "Direct",
    tooltip: "Messages are injected directly as immediate requests.",
    Icon: Send,
  }
}

export function CapabilityBadge({ capabilities }: CapabilityBadgeProps) {
  const { label, tooltip, Icon } = getCapabilityMeta(capabilities)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="secondary" className="font-mono text-xs">
          <Icon className="size-3" />
          {label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="top" sideOffset={6}>
        {tooltip}
      </TooltipContent>
    </Tooltip>
  )
}
