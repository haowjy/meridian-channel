import type { TurnBlock, UserTurn } from "../types"

export const SAMPLE_IMAGE_URL = "https://picsum.photos/seed/meridian-thread-image/960/640"

export const SAMPLE_REFERENCE = {
  refId: "chapter-18",
  refType: "chapter",
  displayText: "Chapter 18: Bell Strike Ritual",
  selectionStart: 120,
  selectionEnd: 312,
}

export const SAMPLE_PARTIAL_REFERENCE = {
  refId: "doc-ritual-notes",
  refType: "document",
  displayText: "Ritual Notes (selection pending)",
}

export function textBlock(id: string, text: string, sequence: number): TurnBlock {
  return {
    id,
    blockType: "text",
    sequence,
    textContent: text,
    status: "complete",
  }
}

export function imageBlock(
  id: string,
  options: {
    sequence: number
    url?: string
    altText?: string
    caption?: string
  },
): TurnBlock {
  return {
    id,
    blockType: "image",
    sequence: options.sequence,
    textContent: options.caption,
    content: {
      url: options.url ?? SAMPLE_IMAGE_URL,
      alt_text: options.altText ?? "Uploaded chapter sketch",
      mime_type: "image/jpeg",
    },
    status: "complete",
  }
}

export function referenceBlock(
  id: string,
  options: {
    sequence: number
    refId?: string
    refType?: string
    displayText?: string
    selectionStart?: number
    selectionEnd?: number
    partial?: boolean
  },
): TurnBlock {
  return {
    id,
    blockType: options.partial ? "partial_reference" : "reference",
    sequence: options.sequence,
    content: {
      ref_id: options.refId ?? SAMPLE_REFERENCE.refId,
      ref_type: options.refType ?? SAMPLE_REFERENCE.refType,
      display_text: options.displayText,
      selection_start: options.selectionStart,
      selection_end: options.selectionEnd,
    },
    status: "complete",
  }
}

export function toolResultBlock(id: string, sequence: number): TurnBlock {
  return {
    id,
    blockType: "tool_result",
    sequence,
    content: {
      tool_use_id: "tool-use-1",
      is_error: false,
      result: "done",
    },
    status: "complete",
  }
}

export function userTurn(blocks: TurnBlock[]): UserTurn {
  return {
    id: "user-turn-1",
    threadId: "thread-1",
    parentId: null,
    status: "complete",
    siblingIds: ["user-turn-1"],
    siblingIndex: 0,
    createdAt: new Date("2026-03-28T09:00:00.000Z"),
    role: "user",
    blocks,
  }
}
