import type { Meta, StoryObj } from "@storybook/react-vite"

import { ActivityBlock } from "./ActivityBlock"
import { COMPLETED_TURN, ERROR_RECOVERY, LONG_TOOL_CHAIN, NESTED_AGENT } from "./examples"
import { bashTool, editTool, genericTool, readTool, searchTool, webSearchTool } from "./examples/factories"
import type { ActivityBlockData } from "./types"

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

const meta = {
  title: "Features/Threads/Activity Block",
  component: ActivityBlock,
  tags: ["autodocs"],
  args: { activity: { id: "default", items: [] } satisfies ActivityBlockData },
} satisfies Meta<typeof ActivityBlock>

export default meta
type Story = StoryObj<typeof meta>

/** Collapsed block with response text below -- the standard completed turn pattern. */
export const CompletedTurn: Story = {
  render: () => (
    <ActivityBlock activity={COMPLETED_TURN} className="max-w-3xl" />
  ),
}

export const LongToolChain: Story = {
  render: () => (
    <ActivityBlock activity={LONG_TOOL_CHAIN} defaultExpanded className="max-w-3xl" />
  ),
}

export const NestedAgent: Story = {
  render: () => (
    <ActivityBlock
      activity={NESTED_AGENT}
      defaultExpanded
      defaultExpandedToolIds={["na-agent-1"]}
      className="max-w-3xl"
    />
  ),
}

export const ErrorRecovery: Story = {
  render: () => (
    <ActivityBlock activity={ERROR_RECOVERY} defaultExpanded className="max-w-3xl" />
  ),
}

/** Streaming turn -- realistic interleaved thinking, text, and tools with mixed statuses. */
export const Streaming: Story = {
  render: () => (
    <ActivityBlock
      activity={{
        id: "streaming",
        isStreaming: true,
        pendingText: "Now let me adjust the bridge paragraph to carry the bell motif forward...",
        items: [
          { kind: "thinking", id: "s-think-1", text: "The user wants me to fix the pacing between chapters 18 and 19. The sparring scene ends abruptly and jumps straight into the meditation hall. I need to check how the transition currently reads and whether there are any sensory anchors I can use as a bridge.\n\nLet me start by reading the end of chapter 19 to see the current state." },
          readTool("s-read-1", "chapters/chapter-19.md"),
          { kind: "thinking", id: "s-think-2", text: "The transition is too abrupt — Mara goes from mid-swing to seated meditation in one paragraph break. There's no decompression beat. The bell motif from the abbey rituals could work as a bridge element, but I need to find where it was first introduced to keep the imagery consistent.\n\nLet me search for the meditation bell references across the manuscript." },
          { kind: "content", id: "s-text-1", text: "I noticed the transition between the sparring and meditation scenes feels rushed. Let me look at how the bell motif was set up earlier." },
          searchTool("s-search-1", "meditation bell", "done"),
          { kind: "thinking", id: "s-think-3", text: "Found the bell motif in chapter 18 — three strikes with specific intervals. The first strike signals awareness, the second signals release, the third signals stillness. This three-beat pattern gives me exactly the structure I need for the transitional paragraph.\n\nI should read the full passage to make sure I get the cadence right before editing." },
          { kind: "content", id: "s-text-2", text: "The bell motif was established in chapter 18 with three strikes. I'll add a transitional beat that echoes that pattern." },
          readTool("s-read-2", "chapters/chapter-18.md"),
          { kind: "thinking", id: "s-think-4", text: "Good — the three-strike pattern is consistent with the abbey's established rituals. I'll write a bridge paragraph that mirrors this cadence: one sentence for the last echo of steel, one for the breath between, one for the first bell. This should make the scene transition feel intentional rather than abrupt." },
          editTool("s-edit-1", "chapters/chapter-19.md", "executing"),
          searchTool("s-search-2", "breath cadence", "executing"),
        ],
      }}
    />
  ),
}

/** All tool detail types in a single block -- starts truncated with "Show more". */
export const AllToolDetails: Story = {
  render: () => (
    <ActivityBlock
      activity={{
        id: "all-details",
        isStreaming: false,
        items: [
          readTool("d-read-1", "chapters/chapter-03.md"),
          editTool("d-edit-1", "chapters/chapter-04.md"),
          searchTool("d-search-1", "river gate motif"),
          webSearchTool("d-web-1", "monastery bell ceremony traditions"),
          bashTool("d-bash-1", "scripts/analyze-motifs.sh"),
          genericTool("d-generic-1", "skill_invoke", { skill_name: "pacing-analysis", chapter: "chapter-19.md" }),
        ],
      }}
      defaultExpanded
    />
  ),
}

/** Edit detail showing diff view. */
export const EditDiff: Story = {
  render: () => (
    <div className="max-w-3xl space-y-4">
      <ActivityBlock
        activity={{
          id: "edit-diff",
          isStreaming: false,
          items: [editTool("ed-1", "chapters/chapter-11.md")],
        }}
        defaultExpanded
        defaultExpandedToolIds={["ed-1"]}
      />
    </div>
  ),
}

/** Nested agent spawn with sub-activity. */
export const AgentSpawn: Story = {
  render: () => (
    <ActivityBlock
      activity={{
        id: "agent-spawn",
        isStreaming: false,
        items: [
          readTool("a-read-1", "notes/world/abbey-rituals.md"),
          {
            kind: "tool",
            id: "a-agent-1",
            toolName: "SpawnAgent",
            status: "done",
            argsText: JSON.stringify({ name: "Continuity Scout", prompt: "Check oath language consistency" }),
            parsedArgs: { name: "Continuity Scout", prompt: "Check oath language consistency" },
            resultText:
              "Found one inconsistency: chapter 19 says 'second oath' while chapter 7 established 'third oath'.",
            nestedActivity: {
              id: "sub-agent-activity",
              isStreaming: false,
              items: [
                readTool("sub-read-1", "chapters/chapter-19.md"),
                searchTool("sub-search-1", "abbey oath"),
              ],
              pendingText: "Cross-checking oath language for consistency.",
            },
          },
        ],
      }}
      defaultExpanded
      defaultExpandedToolIds={["a-agent-1"]}
    />
  ),
}

