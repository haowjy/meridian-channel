import type { TurnBlock, UserTurn } from "../types"

import { ImageBlock } from "./ImageBlock"
import { ReferenceBlock } from "./ReferenceBlock"

function getString(content: Record<string, unknown> | undefined, key: string): string | undefined {
  const value = content?.[key]
  return typeof value === "string" ? value : undefined
}

function getNumber(content: Record<string, unknown> | undefined, key: string): number | undefined {
  const value = content?.[key]
  return typeof value === "number" ? value : undefined
}

function UserBlock({ block }: { block: TurnBlock }) {
  const content = block.content

  switch (block.blockType) {
    case "text":
    case "thinking":
      if (!block.textContent) {
        return null
      }

      return (
        <p className="whitespace-pre-wrap leading-relaxed text-card-foreground">{block.textContent}</p>
      )

    case "image": {
      const imageUrl = getString(content, "url")
      if (!imageUrl) {
        return null
      }

      return (
        <ImageBlock
          url={imageUrl}
          mimeType={getString(content, "mime_type")}
          altText={getString(content, "alt_text")}
          caption={block.textContent}
        />
      )
    }

    case "reference":
    case "partial_reference": {
      const refId = getString(content, "ref_id")
      const refType = getString(content, "ref_type")
      if (!refId || !refType) {
        return null
      }
      const displayText = getString(content, "display_text") ?? getString(content, "title")

      return (
        <ReferenceBlock
          refId={refId}
          refType={refType}
          displayText={displayText}
          selectionStart={getNumber(content, "selection_start")}
          selectionEnd={getNumber(content, "selection_end")}
        />
      )
    }

    case "tool_result":
      return null
    default:
      return null
  }
}

export function UserBubble({ turn }: { turn: UserTurn }) {
  return (
    <div className="flex justify-end">
      <article className="max-w-[95%] space-y-3 rounded-xl border border-border/80 bg-card px-4 py-3 text-sm shadow-sm">
        {turn.blocks.map((block) => (
          <UserBlock key={block.id} block={block} />
        ))}
      </article>
    </div>
  )
}
