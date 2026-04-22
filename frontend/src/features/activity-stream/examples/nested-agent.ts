import { readTool, searchTool } from "./factories"

import type { ActivityBlockData } from "../types"

export const NESTED_AGENT: ActivityBlockData = {
  id: "nested-agent",
  isStreaming: false,
  items: [
    {
      kind: "thinking",
      id: "na-think-1",
      text: "I'll run a continuity scout to verify oath wording while I tune the meditation transition.",
    },
    readTool("na-read-1", "notes/world/abbey-rituals.md"),
    {
      kind: "tool",
      id: "na-agent-1",
      toolName: "SpawnAgent",
      status: "done",
      argsText: JSON.stringify({ name: "Continuity Scout", prompt: "Check oath language consistency" }),
      parsedArgs: { name: "Continuity Scout", prompt: "Check oath language consistency" },
      resultText: "Sub-agent found one mismatch: chapter 19 says 'second oath' while chapter 7 establishes 'third oath'.",
      nestedActivity: {
        id: "na-sub-activity",
        isStreaming: false,
        pendingText: "Cross-checking oath phrases across early chapters.",
        items: [
          searchTool("na-sub-search-1", "abbey oath"),
          readTool("na-sub-read-1", "chapters/chapter-07.md"),
          readTool("na-sub-read-2", "chapters/chapter-19.md"),
          {
            kind: "content",
            id: "na-sub-content-1",
            text: "Mismatch confirmed. Recommend replacing 'second oath' with 'third oath' in chapter 19.",
          },
        ],
      },
    },
    {
      kind: "content",
      id: "na-response",
      text: "I applied the continuity recommendation and kept Mara's meditation transition aligned with the abbey's third-oath language.",
    },
  ],
}
