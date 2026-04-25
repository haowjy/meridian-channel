import { useCallback, useEffect, useRef, useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { ConversationView } from "./ConversationView"
import type { ConversationEntry, UserEntry, AssistantEntry } from "../conversation-types"
import type { ActivityBlockData } from "@/features/activity-stream/types"
import {
  readTool,
  editTool,
  bashTool,
  searchTool,
} from "@/features/activity-stream/examples/factories"
import {
  USER_MESSAGES,
  ASSISTANT_RESPONSES,
  THINKING_FRAGMENTS,
  CHAPTER_PATHS,
  SEARCH_QUERIES,
  BASH_COMMANDS,
} from "@/features/activity-stream/examples/content-pools"

// ---------------------------------------------------------------------------
// Helpers — generate deterministic conversation entries
// ---------------------------------------------------------------------------

function makeUserEntry(index: number): UserEntry {
  return {
    kind: "user",
    id: `user-${index}`,
    text: USER_MESSAGES[index % USER_MESSAGES.length],
    sentAt: new Date(Date.now() - (100 - index) * 60_000),
  }
}

function makeAssistantEntry(index: number): AssistantEntry {
  const activity: ActivityBlockData = {
    id: `activity-${index}`,
    isStreaming: false,
    items: [
      {
        kind: "thinking",
        id: `think-${index}`,
        text: THINKING_FRAGMENTS[index % THINKING_FRAGMENTS.length],
      },
      readTool(`read-${index}`, CHAPTER_PATHS[index % CHAPTER_PATHS.length]),
      searchTool(`search-${index}`, SEARCH_QUERIES[index % SEARCH_QUERIES.length]),
      editTool(`edit-${index}`, CHAPTER_PATHS[(index + 5) % CHAPTER_PATHS.length]),
      {
        kind: "content",
        id: `content-${index}`,
        text: ASSISTANT_RESPONSES[index % ASSISTANT_RESPONSES.length],
      },
    ],
  }

  return {
    kind: "assistant",
    id: `assistant-${index}`,
    activity,
    status: "complete",
  }
}

/** Build N user/assistant turn pairs. */
function buildConversation(turnCount: number): ConversationEntry[] {
  const entries: ConversationEntry[] = []
  for (let i = 0; i < turnCount; i++) {
    entries.push(makeUserEntry(i))
    entries.push(makeAssistantEntry(i))
  }
  return entries
}

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

const meta = {
  title: "Features/Chat/ConversationView",
  component: ConversationView,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story) => (
      <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ConversationView>

export default meta
type Story = StoryObj<typeof meta>

// --- Empty state ---
export const Empty: Story = {
  args: {
    entries: [],
    currentActivity: null,
    isConnecting: false,
  },
}

// --- Connecting state ---
export const Connecting: Story = {
  args: {
    entries: [],
    currentActivity: null,
    isConnecting: true,
  },
}

// --- Few entries (no scroll needed) ---
export const FewEntries: Story = {
  args: {
    entries: buildConversation(2),
    currentActivity: null,
    isConnecting: false,
  },
}

// --- Many entries (virtual scroll exercised) ---
export const ManyEntries: Story = {
  args: {
    entries: buildConversation(20),
    currentActivity: null,
    isConnecting: false,
  },
}

// --- Variable height entries (mix of short and long) ---
export const VariableHeight: Story = {
  args: { entries: [], currentActivity: null, isConnecting: false },
  render: () => {
    const entries: ConversationEntry[] = []
    for (let i = 0; i < 15; i++) {
      // Short user message
      entries.push(makeUserEntry(i))

      if (i % 3 === 0) {
        // Long assistant with many tools
        const activity: ActivityBlockData = {
          id: `var-activity-${i}`,
          isStreaming: false,
          items: [
            { kind: "thinking", id: `var-think-${i}`, text: THINKING_FRAGMENTS[i % THINKING_FRAGMENTS.length] },
            readTool(`var-read-${i}-a`, CHAPTER_PATHS[i % CHAPTER_PATHS.length]),
            readTool(`var-read-${i}-b`, CHAPTER_PATHS[(i + 1) % CHAPTER_PATHS.length]),
            searchTool(`var-search-${i}`, SEARCH_QUERIES[i % SEARCH_QUERIES.length]),
            bashTool(`var-bash-${i}`, BASH_COMMANDS[i % BASH_COMMANDS.length]),
            editTool(`var-edit-${i}`, CHAPTER_PATHS[(i + 2) % CHAPTER_PATHS.length]),
            { kind: "content", id: `var-content-${i}`, text: ASSISTANT_RESPONSES[i % ASSISTANT_RESPONSES.length] + "\n\n" + ASSISTANT_RESPONSES[(i + 1) % ASSISTANT_RESPONSES.length] },
          ],
        }
        entries.push({
          kind: "assistant",
          id: `var-assistant-${i}`,
          activity,
          status: "complete",
        })
      } else {
        // Short assistant — just content
        const activity: ActivityBlockData = {
          id: `var-activity-${i}`,
          isStreaming: false,
          items: [
            { kind: "content", id: `var-content-${i}`, text: ASSISTANT_RESPONSES[i % ASSISTANT_RESPONSES.length] },
          ],
        }
        entries.push({
          kind: "assistant",
          id: `var-assistant-${i}`,
          activity,
          status: "complete",
        })
      }
    }

    return (
      <ConversationView
        entries={entries}
        currentActivity={null}
        isConnecting={false}
      />
    )
  },
}

// --- Streaming simulation (tests auto-scroll + breakaway) ---
export const StreamingSimulation: Story = {
  args: { entries: [], currentActivity: null, isConnecting: false },
  render: function StreamingStory() {
    const [entries, setEntries] = useState<ConversationEntry[]>(() => buildConversation(5))
    const [currentActivity, setCurrentActivity] = useState<ActivityBlockData | null>(null)
    const counterRef = useRef(5)

    const addTurn = useCallback(() => {
      const idx = counterRef.current++

      // First add user message
      setEntries((prev) => [...prev, makeUserEntry(idx)])

      // Then simulate streaming with a live activity after a short delay
      setTimeout(() => {
        const streamingActivity: ActivityBlockData = {
          id: `stream-${idx}`,
          isStreaming: true,
          items: [
            {
              kind: "thinking",
              id: `stream-think-${idx}`,
              text: THINKING_FRAGMENTS[idx % THINKING_FRAGMENTS.length],
            },
            readTool(`stream-read-${idx}`, CHAPTER_PATHS[idx % CHAPTER_PATHS.length], "executing"),
          ],
        }
        setCurrentActivity(streamingActivity)

        // Finish streaming after 2s → freeze as assistant entry
        setTimeout(() => {
          setCurrentActivity(null)
          setEntries((prev) => [...prev, makeAssistantEntry(idx)])
        }, 2000)
      }, 500)
    }, [])

    // Auto-add turns for testing
    useEffect(() => {
      const interval = setInterval(addTurn, 4000)
      return () => clearInterval(interval)
    }, [addTurn])

    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={addTurn}
            style={{ padding: "4px 12px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--card)", cursor: "pointer", fontSize: 13 }}
          >
            Add turn
          </button>
          <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
            Auto-adds every 4s. Scroll away to test breakaway behavior.
          </span>
        </div>
        <ConversationView
          entries={entries}
          currentActivity={currentActivity}
          isConnecting={false}
        />
      </div>
    )
  },
}

// --- Error and cancelled entries ---
export const ErrorAndCancelled: Story = {
  args: { entries: [], currentActivity: null, isConnecting: false },
  render: () => {
    const entries: ConversationEntry[] = [
      makeUserEntry(0),
      makeAssistantEntry(0),
      makeUserEntry(1),
      {
        kind: "assistant",
        id: "error-entry",
        activity: {
          id: "error-activity",
          isStreaming: false,
          items: [
            readTool("err-read", "chapters/chapter-19.md"),
            { kind: "content", id: "err-content", text: "Partial response before error..." },
          ],
          error: "Rate limit exceeded. Please try again in 30 seconds.",
        },
        status: "error",
      },
      makeUserEntry(2),
      {
        kind: "assistant",
        id: "cancelled-entry",
        activity: {
          id: "cancelled-activity",
          isStreaming: false,
          items: [
            { kind: "thinking", id: "cancel-think", text: "Starting analysis..." },
            readTool("cancel-read", "chapters/chapter-07.md", "executing"),
          ],
          isCancelled: true,
        },
        status: "cancelled",
      },
      makeUserEntry(3),
      makeAssistantEntry(3),
    ]

    return (
      <ConversationView
        entries={entries}
        currentActivity={null}
        isConnecting={false}
      />
    )
  },
}
