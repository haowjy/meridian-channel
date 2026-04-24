/**
 * ThreadColumn — one spawn's full chat column (header + activity + composer).
 *
 * Each column owns its own WS connection to the spawn via
 * `useThreadStreaming`. That keeps columns independent: cancelling,
 * streaming, or closing one doesn't disturb siblings.
 *
 * Now chat-aware: when the column's spawn belongs to the currently
 * selected chat, the SpawnHeader shows a chat-context badge.
 *
 * Spawn identity (agent / model / harness / status) is fetched lazily via
 * the `/api/spawns/{id}/details` endpoint. Stories supply `detailsOverride`.
 *
 * Focus feedback: a 2px accent bar slides along the top edge of the
 * focused column. Unfocused columns fade slightly.
 */
import { useCallback, useEffect, useMemo, useState } from "react"

import { SpawnActivityView } from "@/features/threads/components/SpawnActivityView"
import { Composer } from "@/features/threads/composer/Composer"
import type { StreamController } from "@/features/threads/transport-types"
import { useThreadStreaming } from "@/hooks/use-thread-streaming"
import {
  fetchSpawn,
  type SpawnProjection,
} from "@/features/sessions/lib/api"
import { parseStatus, type SpawnStatus } from "@/types/spawn"
import { cn } from "@/lib/utils"

import { SpawnHeader } from "./SpawnHeader"
import { useChat } from "./ChatContext"

export interface ThreadColumnSpawnDetails {
  status: SpawnStatus
  agent: string | null
  model: string | null
  harness: string
}

export interface ThreadColumnProps {
  spawnId: string
  isFocused: boolean
  onClose: () => void
  onFocus: () => void
  className?: string
  /**
   * Storybook / test escape hatch. When provided, skips the
   * `fetchSpawns` lookup and renders with the supplied identity.
   */
  detailsOverride?: ThreadColumnSpawnDetails
}

function projectionToDetails(p: SpawnProjection): ThreadColumnSpawnDetails {
  return {
    status: parseStatus(p.status),
    agent: p.agent || null,
    model: p.model || null,
    harness: p.harness,
  }
}

export function ThreadColumn({
  spawnId,
  isFocused,
  onClose,
  onFocus,
  className,
  detailsOverride,
}: ThreadColumnProps) {
  const { state, capabilities, channel, connectionState } =
    useThreadStreaming(spawnId)

  const chatCtx = useChat()

  const [fetchedDetails, setFetchedDetails] =
    useState<ThreadColumnSpawnDetails | null>(null)

  useEffect(() => {
    if (detailsOverride) {
      setFetchedDetails(null)
      return
    }

    let cancelled = false
    setFetchedDetails(null)

    fetchSpawn(spawnId)
      .then((projection) => {
        if (cancelled) return
        setFetchedDetails(projectionToDetails(projection))
      })
      .catch(() => {
        // Silent — header degrades gracefully when details unknown.
      })

    return () => {
      cancelled = true
    }
  }, [detailsOverride, spawnId])

  const details: ThreadColumnSpawnDetails = detailsOverride ??
    fetchedDetails ?? {
      status: "running",
      agent: null,
      model: null,
      harness: "…",
    }

  const isStreaming = Boolean(state.isStreaming)

  // Resolve chat context for this spawn
  const chatId = chatCtx.selectedChat?.activeSpawnId === spawnId
    ? chatCtx.selectedChat.chatId
    : null

  const controller = useMemo<StreamController>(
    () => ({
      sendMessage: (text) => channel.current?.sendMessage(text) ?? false,
      interrupt: () => channel.current?.interrupt() ?? false,
      cancel: () => {
        channel.current?.cancel()
      },
    }),
    [channel],
  )

  const handleInterrupt = useCallback(() => {
    channel.current?.interrupt()
  }, [channel])

  const handleCancel = useCallback(() => {
    channel.current?.cancel()
  }, [channel])

  const composerDisabled =
    connectionState !== "open" ||
    details.status === "succeeded" ||
    details.status === "failed" ||
    details.status === "cancelled"

  return (
    <div
      onMouseDownCapture={isFocused ? undefined : onFocus}
      onFocusCapture={isFocused ? undefined : onFocus}
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden",
        "rounded-md border border-border bg-background",
        "transition-[box-shadow,opacity] duration-200",
        isFocused
          ? "ring-1 ring-ring/60"
          : "opacity-90 hover:opacity-100",
        className,
      )}
    >
      {/* Focus accent bar */}
      <div
        aria-hidden
        className={cn(
          "absolute inset-x-0 top-0 h-0.5 origin-left bg-accent-fill",
          "transition-transform duration-200 ease-out",
          isFocused ? "scale-x-100" : "scale-x-0",
        )}
      />

      <SpawnHeader
        spawnId={spawnId}
        status={details.status}
        agent={details.agent}
        model={details.model}
        harness={details.harness}
        isStreaming={isStreaming}
        chatId={chatId}
        onInterrupt={handleInterrupt}
        onCancel={handleCancel}
        onClose={onClose}
      />

      <div className="flex min-h-0 flex-1 flex-col gap-2 p-2">
        <div className="min-h-0 flex-1">
          <SpawnActivityView activity={state} />
        </div>

        <Composer
          controller={controller}
          capabilities={capabilities}
          isStreaming={isStreaming}
          disabled={composerDisabled}
        />
      </div>
    </div>
  )
}
