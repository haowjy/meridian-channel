import { bashTool, readTool } from "./factories"

import type { ActivityBlockData } from "../types"

export const ERROR_RECOVERY: ActivityBlockData = {
  id: "error-recovery",
  isStreaming: false,
  items: [
    readTool("er-read-1", "chapters/chapter-19.md"),
    {
      ...bashTool("er-bash-1", "scripts/analyze-pacing.sh chapters/chapter-19.md", "error"),
      isError: true,
      resultText:
        "$ scripts/analyze-pacing.sh chapters/chapter-19.md\nbash: scripts/analyze-pacing.sh: No such file or directory",
    },
    bashTool("er-bash-2", "./scripts/analyze-pacing.sh chapters/chapter-19.md"),
    {
      kind: "content",
      id: "er-response",
      text: "The first pacing pass failed because I called the script with the wrong path. I retried with `./scripts/analyze-pacing.sh`, confirmed the transition metrics, and kept the new Mara bridge paragraph in place.",
    },
  ],
}
