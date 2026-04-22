import { editTool, readTool, searchTool } from "./factories"

import type { ActivityBlockData } from "../types"

export const COMPLETED_TURN: ActivityBlockData = {
  id: "completed-turn",
  isStreaming: false,
  items: [
    readTool("ct-read-1", "chapters/chapter-19.md"),
    searchTool("ct-search-1", "meditation hall"),
    editTool("ct-edit-1", "chapters/chapter-19.md"),
    {
      kind: "content",
      id: "ct-response",
      text: "Here is what I changed to improve pacing in the transition scene between the sparring and meditation sequence: I added a bridge paragraph that carries Mara from noise into stillness with one breath-count beat and a bell cue.",
    },
  ],
}
