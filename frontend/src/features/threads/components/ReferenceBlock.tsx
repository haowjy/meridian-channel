import { FileText } from "@phosphor-icons/react"

type ReferenceBlockProps = {
  refId: string
  refType: string
  displayText?: string
  selectionStart?: number
  selectionEnd?: number
}

function getReferenceLabel(displayText: string | undefined, refType: string): string {
  if (displayText && displayText.trim()) {
    return displayText
  }

  return `${refType} reference`
}

export function ReferenceBlock({
  refId,
  refType,
  displayText,
  selectionStart,
  selectionEnd,
}: ReferenceBlockProps) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-accent-fill/25 bg-accent-fill/10 px-2 py-0.5 text-sm text-accent-text"
      data-ref-id={refId}
      data-ref-type={refType}
      data-selection-start={selectionStart}
      data-selection-end={selectionEnd}
      title={refId}
    >
      <FileText className="size-3.5 shrink-0" aria-hidden="true" />
      <span>{getReferenceLabel(displayText, refType)}</span>
    </span>
  )
}
