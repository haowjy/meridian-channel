import type { ContentItem } from "../types"

type ContentRowProps = {
  item: ContentItem
}

export function ContentRow({ item }: ContentRowProps) {
  return (
    <div className="grid grid-cols-[1.375rem_1fr_auto] px-3">
      <div className="col-span-3 py-2 pl-[11px]">
        <p className="text-sm text-muted-foreground">{item.text}</p>
      </div>
    </div>
  )
}
