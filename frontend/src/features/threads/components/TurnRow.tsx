import { Badge } from "@/components/ui/badge"
import { ActivityBlock } from "@/features/activity-stream"

import type { AssistantTurn, ThreadTurn } from "../types"

import { PendingTurn } from "./PendingTurn"
import { SiblingNav } from "./SiblingNav"
import { TurnStatusBanner } from "./TurnStatusBanner"
import { UserBubble } from "./UserBubble"

type TurnRowProps = {
  turn: ThreadTurn
  onSwitchSibling?: (targetTurnId: string) => void
}

function hasRenderableActivity(turn: AssistantTurn): boolean {
  return turn.activity.items.length > 0 || Boolean(turn.activity.pendingText)
}

function ErrorTurn({ turn }: { turn: AssistantTurn }) {
  const errorMessage = turn.error ?? "An unexpected error interrupted this response."

  return (
    <div className="space-y-2">
      <TurnStatusBanner variant="error" message={errorMessage} />
      {hasRenderableActivity(turn) ? <ActivityBlock activity={turn.activity} /> : null}
    </div>
  )
}

function CancelledTurn({ turn }: { turn: AssistantTurn }) {
  return (
    <div className="space-y-2 opacity-70">
      <div className="flex items-center gap-2">
        <TurnStatusBanner variant="warning" message="This response was cancelled." className="flex-1" />
        <Badge
          variant="outline"
          className="border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300"
        >
          Cancelled
        </Badge>
      </div>
      {hasRenderableActivity(turn) ? <ActivityBlock activity={turn.activity} /> : null}
    </div>
  )
}

function CreditLimitedTurn({ turn }: { turn: AssistantTurn }) {
  return (
    <div className="space-y-2">
      <TurnStatusBanner variant="warning" message={turn.error ?? "Credit limit reached."} />
      {hasRenderableActivity(turn) ? <ActivityBlock activity={turn.activity} /> : null}
    </div>
  )
}

export function TurnRow({ turn, onSwitchSibling }: TurnRowProps) {
  const hasSiblings = turn.siblingIds.length > 1
  const previousSiblingId = hasSiblings ? turn.siblingIds[turn.siblingIndex - 1] : undefined
  const nextSiblingId = hasSiblings ? turn.siblingIds[turn.siblingIndex + 1] : undefined

  const handlePrevious = previousSiblingId
    ? () => {
        onSwitchSibling?.(previousSiblingId)
      }
    : undefined

  const handleNext = nextSiblingId
    ? () => {
        onSwitchSibling?.(nextSiblingId)
      }
    : undefined

  if (turn.role === "system") {
    return null
  }

  const content =
    turn.role === "assistant" ? (
      turn.status === "pending" ? (
        <PendingTurn />
      ) : turn.status === "error" ? (
        <ErrorTurn turn={turn} />
      ) : turn.status === "cancelled" ? (
        <CancelledTurn turn={turn} />
      ) : turn.status === "credit_limited" ? (
        <CreditLimitedTurn turn={turn} />
      ) : (
        <div>
          <ActivityBlock
            // Remount when transitioning out of waiting_subagents so internal
            // expanded state resets to the default for the new status.
            key={turn.status === "waiting_subagents" ? `${turn.id}-waiting` : turn.id}
            activity={turn.activity}
            isWaitingSubagents={turn.status === "waiting_subagents"}
            defaultExpanded={turn.status === "waiting_subagents"}
          />
        </div>
      )
    ) : (
      <UserBubble turn={turn} />
    )

  return (
    <div className="min-w-0">
      {hasSiblings ? (
        <SiblingNav
          current={turn.siblingIndex}
          total={turn.siblingIds.length}
          onPrevious={handlePrevious}
          onNext={handleNext}
        />
      ) : null}

      {content}
    </div>
  )
}
