import { AlertCircle } from "lucide-react"

interface ErrorItemProps {
  message: string
}

export function ErrorItem({ message }: ErrorItemProps) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-destructive">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="text-sm leading-relaxed">{message}</p>
    </div>
  )
}
