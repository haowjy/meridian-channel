/**
 * ZeroStateGreeting — centered greeting shown when no chat is active.
 *
 * Minimal editorial layout: a warm heading + subtle prompt,
 * anchored vertically in the available space.
 */

import { cn } from "@/lib/utils"

export interface ZeroStateGreetingProps {
  className?: string
}

export function ZeroStateGreeting({ className }: ZeroStateGreetingProps) {
  return (
    <div
      className={cn(
        "flex flex-1 items-center justify-center px-6",
        className,
      )}
    >
      <div className="max-w-md text-center">
        {/* Decorative dot — jade accent */}
        <div
          className="mx-auto mb-5 size-2 rounded-full bg-accent-fill opacity-70"
          aria-hidden
        />

        <h2 className="font-editor text-2xl font-semibold tracking-tight text-foreground">
          How can I help you?
        </h2>

        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Select a model and start a conversation.
        </p>
      </div>
    </div>
  )
}
