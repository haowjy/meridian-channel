const DOT_DELAYS_MS = [0, 180, 360]

export function PendingTurn() {
  return (
    <div className="pr-10" role="status" aria-live="polite">
      <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-card/75 px-4 py-3 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5" aria-hidden="true">
          {DOT_DELAYS_MS.map((delayMs) => (
            <span
              key={delayMs}
              className="size-1.5 rounded-full bg-muted-foreground/80 animate-pulse"
              style={{ animationDelay: `${delayMs}ms` }}
            />
          ))}
        </span>
        <span>Thinking...</span>
      </div>
    </div>
  )
}
