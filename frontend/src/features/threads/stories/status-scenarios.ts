import type { ActivityBlockData } from "@/features/activity-stream/types"

import type { AssistantTurn, TurnStatus } from "@/features/threads/types"

const THREAD_ID = "thread-status-scenarios"
const CREATED_AT = new Date("2026-03-28T09:00:00.000Z")

function assistantTurn(
  id: string,
  status: TurnStatus,
  activity: ActivityBlockData,
  error?: string,
): AssistantTurn {
  return {
    id,
    threadId: THREAD_ID,
    parentId: "status-parent",
    role: "assistant",
    status,
    siblingIds: [id],
    siblingIndex: 0,
    createdAt: CREATED_AT,
    model: "gpt-5.4-mini",
    activity,
    error,
  }
}

export const STATUS_SCENARIO_TURNS: Record<TurnStatus, AssistantTurn> = {
  pending: assistantTurn("status-pending", "pending", {
    id: "status-pending-activity",
    items: [],
    isStreaming: true,
  }),
  streaming: assistantTurn("status-streaming", "streaming", {
    id: "status-streaming-activity",
    isStreaming: true,
    pendingText: "I am drafting the bridge paragraph now...",
    items: [
      {
        kind: "thinking",
        id: "status-streaming-thinking",
        text: "Need a one-paragraph transition from sparring cadence into stillness.",
      },
      {
        kind: "tool",
        id: "status-streaming-tool",
        toolName: "Read",
        status: "executing",
        argsText: "{\"file_path\":\"chapters/chapter-19.md\"}",
        parsedArgs: { file_path: "chapters/chapter-19.md" },
      },
    ],
  }),
  waiting_subagents: assistantTurn("status-waiting", "waiting_subagents", {
    id: "status-waiting-activity",
    isStreaming: false,
    items: [
      {
        kind: "tool",
        id: "status-waiting-tool-1",
        toolName: "Read",
        status: "done",
        argsText: "{\"file_path\":\"chapters/chapter-19.md\"}",
        parsedArgs: { file_path: "chapters/chapter-19.md" },
        resultText: "Transition between scenes is abrupt in paragraph 42.",
      },
      {
        kind: "tool",
        id: "status-waiting-tool-2",
        toolName: "SpawnAgent",
        status: "executing",
        argsText: "{\"name\":\"Continuity Scout\"}",
        parsedArgs: { name: "Continuity Scout" },
      },
      {
        kind: "content",
        id: "status-waiting-content",
        text: "I found the pacing break. Waiting on supporting checks from sub-agents.",
      },
    ],
  }),
  complete: assistantTurn("status-complete", "complete", {
    id: "status-complete-activity",
    isStreaming: false,
    items: [
      {
        kind: "tool",
        id: "status-complete-tool",
        toolName: "doc_search",
        status: "done",
        argsText: "{\"pattern\":\"meditation bell\",\"path\":\"chapters/\"}",
        parsedArgs: { pattern: "meditation bell", path: "chapters/" },
        resultText: "chapter-18.md:44: three-strike bell motif established.",
      },
      {
        kind: "content",
        id: "status-complete-content",
        text: "The transition now lands on the bell cadence and preserves Mara's restrained voice.",
      },
    ],
  }),
  cancelled: assistantTurn("status-cancelled", "cancelled", {
    id: "status-cancelled-activity",
    isStreaming: false,
    items: [
      {
        kind: "tool",
        id: "status-cancelled-tool",
        toolName: "Read",
        status: "done",
        argsText: "{\"file_path\":\"chapters/chapter-19.md\"}",
        parsedArgs: { file_path: "chapters/chapter-19.md" },
        resultText: "Read complete.",
      },
      {
        kind: "content",
        id: "status-cancelled-content",
        text: "I was midway through drafting the bridge paragraph when this run was cancelled.",
      },
    ],
  }),
  error: assistantTurn(
    "status-error",
    "error",
    {
      id: "status-error-activity",
      isStreaming: false,
      items: [
        {
          kind: "tool",
          id: "status-error-tool",
          toolName: "EditDocument",
          status: "error",
          argsText: "{\"file_path\":\"chapters/chapter-19.md\"}",
          parsedArgs: { file_path: "chapters/chapter-19.md" },
          resultText: "Write failed: lock timeout.",
          isError: true,
        },
        {
          kind: "content",
          id: "status-error-content",
          text: "I prepared the transition draft but could not persist it.",
        },
      ],
    },
    "Database write failed: lock timeout.",
  ),
  credit_limited: assistantTurn(
    "status-credit-limited",
    "credit_limited",
    {
      id: "status-credit-limited-activity",
      isStreaming: false,
      items: [
        {
          kind: "tool",
          id: "status-credit-limited-tool",
          toolName: "Read",
          status: "done",
          argsText: "{\"file_path\":\"chapters/chapter-18.md\"}",
          parsedArgs: { file_path: "chapters/chapter-18.md" },
          resultText: "Read complete.",
        },
        {
          kind: "content",
          id: "status-credit-limited-content",
          text: "I gathered context, but generation stopped because credits were exhausted.",
        },
      ],
    },
    "Credit limit reached for this workspace.",
  ),
}

export const TURN_STATUS_ORDER: TurnStatus[] = [
  "pending",
  "streaming",
  "waiting_subagents",
  "complete",
  "cancelled",
  "error",
  "credit_limited",
]
