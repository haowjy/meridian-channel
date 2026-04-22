import { bashTool, editTool, readTool, searchTool } from "./factories"

import type { ActivityBlockData } from "../types"

export const LONG_TOOL_CHAIN: ActivityBlockData = {
  id: "long-tool-chain",
  isStreaming: false,
  items: [
    {
      kind: "thinking",
      id: "ltc-think-1",
      text: "I need to smooth Mara's emotional descent from sparring intensity into monastery stillness while preserving the established bell cadence.",
    },
    readTool("ltc-read-1", "chapters/chapter-18.md"),
    searchTool("ltc-search-1", "meditation bell"),
    readTool("ltc-read-2", "chapters/chapter-19.md"),
    bashTool("ltc-bash-1", "scripts/analyze-pacing.sh chapters/chapter-19.md"),
    editTool("ltc-edit-1", "chapters/chapter-19.md"),
    searchTool("ltc-search-2", "breath count"),
    readTool("ltc-read-3", "notes/world/abbey-rituals.md"),
    editTool("ltc-edit-2", "chapters/chapter-19.md"),
    bashTool("ltc-bash-2", "scripts/check-voice.sh chapters/chapter-19.md"),
    {
      kind: "content",
      id: "ltc-text-1",
      text: "I tightened the bridge language once; now I am checking continuity beats before the final pass.",
    },
    readTool("ltc-read-4", "chapters/chapter-07.md"),
    searchTool("ltc-search-3", "third bell"),
    bashTool("ltc-bash-3", "scripts/continuity-scan.sh --character Mara --chapter 19"),
    editTool("ltc-edit-3", "chapters/chapter-19.md"),
    readTool("ltc-read-5", "notes/character-notes/mara.md"),
    searchTool("ltc-search-4", "oath language"),
    editTool("ltc-edit-4", "chapters/chapter-19.md"),
    bashTool("ltc-bash-4", "scripts/analyze-rhythm.sh chapters/chapter-19.md"),
    editTool("ltc-edit-5", "chapters/chapter-19.md"),
    {
      kind: "thinking",
      id: "ltc-think-2",
      text: "The rhythm pass now lands on three beats: steel echo, breath reset, first bell. I can deliver the final revision summary.",
    },
    {
      kind: "content",
      id: "ltc-response",
      text: "Completed a full pacing chain across chapter text, ritual notes, and continuity scripts. The transition now uses a clear three-beat descent that matches Mara's established voice and abbey cadence.",
    },
  ],
}
