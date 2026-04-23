/**
 * ThreadColumn — one spawn's full chat column (header + activity + composer).
 *
 * Each column owns its own WS connection to the spawn via
 * `useThreadStreaming`. That keeps columns independent: cancelling,
 * streaming, or closing one doesn't disturb siblings. The column is a
 * thin shell that composes existing pieces — SpawnHeader, SpawnActivityView,
 * Composer — and wires a StreamController bridge from the SpawnChannel
 * instance to the Composer's transport-neutral interface.
 *
 * Spawn identity (agent / model / harness / status) is fetched lazily via
 * the `/api/spawns/{id}/details` endpoint which returns the full projection.
 * Stories supply `detailsOverride` to skip the fetch entirely.
 *
 * Focus feedback is deliberately restrained: a 2px accent bar slides in
 * along the top edge of the focused column. Unfocused columns fade
 * slightly so the eye's attention tracks the composer target without
 * obscuring the streaming content in the others.
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

  const [fetchedDetails, setFetchedDetails] =
    useState<ThreadColumnSpawnDetails | null>(null)

  // Resolve spawn identity. Override wins; otherwise fetch from the list
  // endpoint and filter client-side. We re-fetch when the id changes.
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
      {/* Focus accent — a thin bar that slides in along the top edge. */}
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
