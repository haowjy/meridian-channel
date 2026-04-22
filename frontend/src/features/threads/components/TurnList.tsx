import type { ThreadTurn } from "../types"

import { TurnRow } from "./TurnRow"

type TurnListProps = {
  turns: ThreadTurn[]
  onSwitchSibling?: (targetTurnId: string) => void
}

export function TurnList({ turns, onSwitchSibling }: TurnListProps) {
  return (
    <div className="min-w-0 space-y-4">
      {turns.map((turn) => (
        <TurnRow key={turn.id} turn={turn} onSwitchSibling={onSwitchSibling} />
      ))}
    </div>
  )
}
