/**
 * Realistic AG-UI event scenario for the streaming demo.
 *
 * Simulates an assistant fixing pacing in a chapter transition:
 * 1. Thinking about the problem
 * 2. Read the chapter
 * 3. Search for the bell motif
 * 4. Explain the plan (text)
 * 5. Edit the chapter (diff streams in progressively)
 * 6. Bash analysis tool (parallel with edit result)
 * 7. Final response text
 *
 * Timing is compressed but proportional — args stream at ~30ms/chunk,
 * pauses between actions are 200-500ms.
 */

import type { TimelineEntry } from "../streaming/types"

// Helper to build the timeline incrementally
function buildTimeline(): TimelineEntry[] {
  const entries: TimelineEntry[] = []
  let t = 0

  function at(delay: number, event: TimelineEntry["event"]) {
    t += delay
    entries.push({ delayMs: t, event })
  }

  // ── Run starts ──────────────────────────────────────────────
  at(0, { type: "RUN_STARTED" })

  // ── Thinking ────────────────────────────────────────────────
  at(200, { type: "THINKING_START", thinkingId: "t1" })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t1",
    delta: "The user wants me to fix the pacing ",
  })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t1",
    delta: "between chapters 18 and 19. The sparring ",
  })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t1",
    delta: "scene ends abruptly and jumps straight into ",
  })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t1",
    delta: "the meditation hall. Let me check the current state.",
  })
  at(100, { type: "THINKING_TEXT_MESSAGE_END", thinkingId: "t1" })

  // ── Text: narration ─────────────────────────────────────────
  at(200, { type: "TEXT_MESSAGE_START", messageId: "m1" })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m1", delta: "I'll look at " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m1", delta: "the transition " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m1", delta: "in chapter 19 first." })
  at(100, { type: "TEXT_MESSAGE_END", messageId: "m1" })

  // ── Tool: Read ──────────────────────────────────────────────
  // Args stream progressively: Read() → Read("chapters/") → Read("chapters/chapter-19.md")
  at(150, { type: "TOOL_CALL_START", toolCallId: "tc1", toolCallName: "Read" })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc1", delta: '{"file_' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc1", delta: 'path": "chapters/' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc1", delta: 'chapter-19' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc1", delta: '.md"}' })
  at(50, { type: "TOOL_CALL_END", toolCallId: "tc1" })
  // Simulate execution time
  at(600, {
    type: "TOOL_CALL_RESULT",
    toolCallId: "tc1",
    content:
      "The rain eased into a silver mist over East Gate.\nMara counted six breaths before stepping into the courtyard.\nA temple bell carried through the wet stone arcades.\n\n---\n\nShe crossed the bridge quickly and looked back once.\nThe transition felt abrupt but she ignored it.\nMaster Ren waited beside the cedar table with two cups of tea.",
  })

  // ── Tool: Search ────────────────────────────────────────────
  at(200, { type: "TOOL_CALL_START", toolCallId: "tc2", toolCallName: "doc_search" })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc2", delta: '{"pattern": "meditation ' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc2", delta: 'bell", ' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc2", delta: '"path": "chapters/"}' })
  at(50, { type: "TOOL_CALL_END", toolCallId: "tc2" })
  at(500, {
    type: "TOOL_CALL_RESULT",
    toolCallId: "tc2",
    content:
      "chapters/chapter-18.md:44: ...the sparring match ended just before the meditation bell rang...\nchapters/chapter-18.md:67: Three strikes — awareness, release, stillness.\nnotes/character-notes/lin.md:12: Lin slows scenes with ritual gestures before major revelations.",
  })

  // ── More thinking ───────────────────────────────────────────
  at(150, { type: "THINKING_START", thinkingId: "t2" })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t2",
    delta: "Found the three-strike bell pattern in chapter 18. ",
  })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t2",
    delta: "I can use this as a bridge — one beat for the echo of steel, ",
  })
  at(40, {
    type: "THINKING_TEXT_MESSAGE_CONTENT",
    thinkingId: "t2",
    delta: "one for the breath, one for the first bell.",
  })
  at(100, { type: "THINKING_TEXT_MESSAGE_END", thinkingId: "t2" })

  // ── Text: plan ──────────────────────────────────────────────
  at(200, { type: "TEXT_MESSAGE_START", messageId: "m2" })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: "The bell motif " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: "from chapter 18 " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: "gives us the perfect " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: "bridge structure. " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: "I'll add a transitional beat." })
  at(100, { type: "TEXT_MESSAGE_END", messageId: "m2" })

  // ── Tool: Edit ──────────────────────────────────────────────
  // Args stream slowly — old_string and new_string build up visibly
  at(150, { type: "TOOL_CALL_START", toolCallId: "tc3", toolCallName: "EditDocument" })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: '{"file_path": "' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "chapters/chapter-19.md" })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: '", "old_string": "' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "She crossed the bridge " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "quickly and looked back once." })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "\\nThe transition felt abrupt " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: 'but she ignored it.", ' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: '"new_string": "' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "She paused on the bridge, " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "letting the drums fade " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "behind her." })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "\\nOnly then did she step " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "into the hush of the " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "monastery hall." })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: "\\nThe slower transition " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc3", delta: 'gave the scene room to breathe."}' })
  at(50, { type: "TOOL_CALL_END", toolCallId: "tc3" })
  at(400, {
    type: "TOOL_CALL_RESULT",
    toolCallId: "tc3",
    content: "Edit applied successfully.",
  })

  // ── Tool: Bash (starts while edit result arrives) ───────────
  at(100, { type: "TOOL_CALL_START", toolCallId: "tc4", toolCallName: "Bash" })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc4", delta: '{"command": "scripts/' })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc4", delta: "analyze-pacing.sh " })
  at(30, { type: "TOOL_CALL_ARGS", toolCallId: "tc4", delta: 'chapters/chapter-19.md"}' })
  at(50, { type: "TOOL_CALL_END", toolCallId: "tc4" })
  at(800, {
    type: "TOOL_CALL_RESULT",
    toolCallId: "tc4",
    content:
      "$ scripts/analyze-pacing.sh chapters/chapter-19.md\nScene transition analysis:\n  Scene 2 → 3: IMPROVED (was: abrupt, now: gradual)\n  Bridge paragraph: 87 words (target: 80-140)\n  Sensory anchors: bell, drums, breath (3/3 ✓)\nOverall pacing score: 8.2/10 (was 4.1/10)",
  })

  // ── Final response ──────────────────────────────────────────
  at(300, { type: "TEXT_MESSAGE_START", messageId: "m3" })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "Done! I added " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "a bridge paragraph " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "that carries Mara " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "from the sparring " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "noise into stillness " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "using the three-strike " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "bell motif from chapter 18. " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "The pacing analysis " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "confirms the transition " })
  at(30, { type: "TEXT_MESSAGE_CONTENT", messageId: "m3", delta: "scores much better now." })
  at(100, { type: "TEXT_MESSAGE_END", messageId: "m3" })

  // ── Done ────────────────────────────────────────────────────
  at(200, { type: "RUN_FINISHED" })

  return entries
}

export const PACING_FIX_SCENARIO = buildTimeline()
