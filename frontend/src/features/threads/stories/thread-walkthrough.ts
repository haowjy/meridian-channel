import type { ActivityBlockData } from "@/features/activity-stream/types"

import { readTool, searchTool } from "@/features/activity-stream/examples/factories"
import { PACING_FIX_SCENARIO } from "@/features/activity-stream/examples/streaming-scenario"

import type { AssistantTurn, ThreadTurn, TurnBlock, UserTurn } from "@/features/threads"

const THREAD_ID = "thread-walkthrough"

function userTextBlock(id: string, sequence: number, text: string): TurnBlock {
  return {
    id,
    blockType: "text",
    sequence,
    textContent: text,
    status: "complete",
  }
}

function userReferenceBlock(id: string, sequence: number): TurnBlock {
  return {
    id,
    blockType: "reference",
    sequence,
    content: {
      ref_type: "file",
      ref_id: "chapters/chapter-19.md",
      title: "chapter-19.md",
      selection_start: 412,
      selection_end: 560,
    },
    status: "complete",
  }
}

function userTurn(
  id: string,
  parentId: string | null,
  createdAt: string,
  blocks: TurnBlock[],
  siblingIds: string[] = [id],
  siblingIndex = 0,
): UserTurn {
  return {
    id,
    threadId: THREAD_ID,
    parentId,
    role: "user",
    status: "complete",
    siblingIds,
    siblingIndex,
    createdAt: new Date(createdAt),
    blocks,
  }
}

function assistantHistoryTurn(
  id: string,
  parentId: string,
  createdAt: string,
  activity: ActivityBlockData,
): AssistantTurn {
  return {
    id,
    threadId: THREAD_ID,
    parentId,
    role: "assistant",
    status: "complete",
    siblingIds: [id],
    siblingIndex: 0,
    createdAt: new Date(createdAt),
    activity,
    model: "gpt-5.4-mini",
    inputTokens: 944,
    outputTokens: 511,
  }
}

const HISTORY_TURNS: ThreadTurn[] = [
  userTurn("turn-01", null, "2026-03-27T09:12:00.000Z", [
    userTextBlock(
      "turn-01-block-01",
      0,
      "I keep tripping over the handoff in Chapter 19. The sparring yard sequence has heat and motion, then two lines later Mara is already in stillness at the monastery table and it feels like I dropped a page. I do not need a full rewrite yet; can you diagnose exactly where the pacing break happens and suggest one bridge paragraph that carries the emotional momentum forward?",
    ),
  ]),
  assistantHistoryTurn("turn-02", "turn-01", "2026-03-27T09:12:21.000Z", {
    id: "turn-02",
    isStreaming: false,
    items: [
      readTool("turn-02-tool-read", "chapters/chapter-19.md"),
      searchTool("turn-02-tool-search", "meditation bell"),
      {
        kind: "content",
        id: "turn-02-content",
        text: "The pacing break sits at line 247, right after \"steel rang one last time against the practice post.\" You jump from peak kinaesthetic intensity — sweat, grip, the vibration up her forearm — to Mara already seated with tea cooling in front of her. There is no deceleration; readers lose roughly 40 minutes of story time in a single paragraph break.\n\nThe bell motif from Chapter 14 is your natural bridge. It already carries associations of forced stillness (Mara hates the bell but obeys it), so reintroducing it here would give her body a reason to transition: she hears the bell, has to stop mid-swing, and the physical comedown becomes the emotional comedown. One paragraph of 90–120 words should be enough — any longer and you risk over-explaining what the reader can feel.",
      },
    ],
  }),
  userTurn("turn-03", "turn-02", "2026-03-27T09:13:01.000Z", [
    userTextBlock(
      "turn-03-block-01",
      0,
      "Use the highlighted excerpt as the anchor point. The prose itself is close, but the rhythm is not: I jump from steel-on-steel intensity straight to tea-table quiet, so Mara reads like she emotionally teleports instead of choosing to slow down. Please keep her voice restrained, avoid modern wording, and keep the bell motif subtle if you reuse it.",
    ),
    userReferenceBlock("turn-03-block-02", 1),
  ]),
  assistantHistoryTurn("turn-04", "turn-03", "2026-03-27T09:13:25.000Z", {
    id: "turn-04",
    isStreaming: false,
    items: [
      {
        kind: "content",
        id: "turn-04-content",
        text: "Good constraints. Here is the plan before I draft:\n\nThe bridge will use three beats, each one decelerating Mara's internal rhythm:\n\n1. **Echo of steel** — the practice post still vibrating, her grip loosening involuntarily. This is the last sensory thread from the sparring yard.\n2. **Breath reset** — she counts four breaths the way her instructor taught, which forces the reader's tempo down without narrating \"she calmed down.\"\n3. **First bell strike** — arriving from outside, pulling her attention outward. This is the hinge into the meditation scene.\n\nI will keep the diction period-appropriate (no \"adrenaline,\" no \"processing\") and hold Mara in close third throughout so the reader feels the slowdown rather than observing it.",
      },
    ],
  }),
  userTurn(
    "turn-05",
    "turn-04",
    "2026-03-27T09:13:47.000Z",
    [
      userTextBlock(
        "turn-05-block-01",
        0,
        "This is close, but the middle beat reads a little explained instead of felt.\n\nI want Mara to register the shift through concrete sensations rather than summary language, and I need the transition to preserve the same quiet, disciplined tone as the rest of Chapter 19. Give me two options between 90 and 120 words: one that emphasizes sound (drums fading, bell entering), and one that emphasizes body rhythm (breath, stance release).",
      ),
    ],
    ["turn-05", "turn-05-sibling-alt"],
    0,
  ),
  assistantHistoryTurn("turn-05a", "turn-05", "2026-03-27T09:14:11.000Z", {
    id: "turn-05a",
    isStreaming: false,
    items: [
      readTool("turn-05a-tool-read", "chapters/chapter-19.md"),
      {
        kind: "content",
        id: "turn-05a-content",
        text: "Two variants below. Both sit at ~110 words and land on the bell.\n\n**Option A — Sound-led:**\nThe last strike held a note she had not expected, high and clean, ringing past the edge of the yard and into the covered walk beyond. Mara let the practice sword drop to her side. Somewhere a dove resettled. The yard was loud with absence now — no feet on packed earth, no counted breath but her own — and into that quiet the evening bell spoke once. She wiped her palm on the wrap at her wrist, set the sword across the post, and followed the sound through the gate.\n\n**Option B — Body-led:**\nHer wrist unlocked first. Then her shoulders, then the long muscles along her spine, each releasing in the order her instructor had drilled years before the yard existed. Mara stood the practice sword against the post and pressed both palms flat on the wood until the grain bit her skin and she was certain her hands were her own again. Sweat cooled at her temples. A dove called from the eaves. When the evening bell struck she was already turning toward the covered walk, her breathing settled into the four-count rhythm the monastery demanded of everyone who entered.",
      },
    ],
  }),
  userTurn("turn-05b", "turn-05a", "2026-03-27T09:14:30.000Z", [
    userTextBlock("turn-05b-block-01", 0, "Actually, cut the second beat entirely."),
  ]),
  assistantHistoryTurn("turn-05c", "turn-05b", "2026-03-27T09:14:46.000Z", {
    id: "turn-05c",
    isStreaming: false,
    items: [
      {
        kind: "content",
        id: "turn-05c-content",
        text: "Cutting it. The two-beat version goes straight from steel ring → bell strike with no breath-count interlude. The risk is that the transition feels abrupt again (the breath was doing deceleration work), so I will compensate by letting the steel's resonance linger a half-sentence longer before the bell enters. That way the reader still feels time passing without a named beat filling it.",
      },
    ],
  }),
  userTurn("turn-05d", "turn-05c", "2026-03-27T09:15:03.000Z", [
    userTextBlock(
      "turn-05d-block-01",
      0,
      "Wait, I changed my mind after rereading the next scene. Keep a tiny second beat, but make it only a half-line so the cadence still moves. Final request: one polished paragraph around 100 to 120 words, stay in Mara's close perspective, and land the paragraph on the first bell strike so it can flow directly into the meditation scene.",
    ),
  ]),
]

// Same streaming data as the Streaming Editor story — one scenario, two views.
const ACTIVE_TIMELINE = PACING_FIX_SCENARIO

export const THREAD_WALKTHROUGH_ACTIVE_TURN_ID = "turn-06"

export const THREAD_WALKTHROUGH = {
  threadId: THREAD_ID,
  history: HISTORY_TURNS,
  activeTimeline: ACTIVE_TIMELINE,
  activeTurnId: THREAD_WALKTHROUGH_ACTIVE_TURN_ID,
}
