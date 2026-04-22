type ImageBlockProps = {
  url: string
  mimeType?: string
  altText?: string
  caption?: string
}

export function ImageBlock({ url, altText, caption }: ImageBlockProps) {
  return (
    <figure className="space-y-2">
      <img
        src={url}
        alt={altText ?? "User attached image"}
        className="max-h-80 max-w-full rounded-md border border-border/70 bg-background/40"
        loading="lazy"
        decoding="async"
      />
      {caption ? <figcaption className="text-xs text-muted-foreground">{caption}</figcaption> : null}
    </figure>
  )
}
