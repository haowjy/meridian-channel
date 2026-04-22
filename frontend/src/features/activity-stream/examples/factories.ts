import type { ToolItem } from "../types"

export function readTool(id: string, filePath: string, status: ToolItem["status"] = "done"): ToolItem {
  const args = { file_path: filePath }
  return {
    kind: "tool",
    id,
    toolName: "Read",
    status,
    argsText: JSON.stringify(args),
    parsedArgs: args,
    resultText:
      status === "done"
        ? "The rain eased into a silver mist over East Gate.\nMara counted six breaths before stepping into the courtyard.\nA temple bell carried through the wet stone arcades."
        : undefined,
  }
}

export function editTool(id: string, filePath: string, status: ToolItem["status"] = "done"): ToolItem {
  const args = {
    file_path: filePath,
    old_string: "She crossed the bridge quickly and looked back once.\nThe transition felt abrupt but she ignored it.",
    new_string:
      "She paused on the bridge, letting the drums fade behind her.\nOnly then did she step into the hush of the monastery hall.\nThe slower transition gave the scene room to breathe.",
  }
  return {
    kind: "tool",
    id,
    toolName: "EditDocument",
    status,
    argsText: JSON.stringify(args),
    parsedArgs: args,
    resultText: status === "done" ? "Edit applied successfully." : undefined,
  }
}

export function searchTool(id: string, query: string, status: ToolItem["status"] = "done"): ToolItem {
  const args = { pattern: query, path: "chapters/" }
  return {
    kind: "tool",
    id,
    toolName: "doc_search",
    status,
    argsText: JSON.stringify(args),
    parsedArgs: args,
    resultText:
      status === "done"
        ? "chapters/chapter-18.md:44: ...the sparring match ended just before the meditation bell rang...\nnotes/character-notes/lin.md:12: Lin slows scenes with ritual gestures before major revelations."
        : undefined,
  }
}

export function webSearchTool(id: string, query: string, status: ToolItem["status"] = "done"): ToolItem {
  const args = { query }
  return {
    kind: "tool",
    id,
    toolName: "web_search",
    status,
    argsText: JSON.stringify(args),
    parsedArgs: args,
    resultText:
      status === "done"
        ? "Zen Meditation Bell Ceremonies - Buddhist Traditions\nhttps://example.com/meditation-bells\nThe meditation bell (keisu) is struck three times to signal the beginning of zazen.\n\nMonastery Courtyards in East Asian Architecture\nhttps://example.com/monastery-architecture\nStone arcades surrounding monastery courtyards served both practical and spiritual purposes."
        : undefined,
  }
}

export function bashTool(id: string, command: string, status: ToolItem["status"] = "done"): ToolItem {
  const args = { command }
  return {
    kind: "tool",
    id,
    toolName: "Bash",
    status,
    argsText: JSON.stringify(args),
    parsedArgs: args,
    resultText:
      status === "done"
        ? "$ scripts/analyze-pacing.sh chapters/chapter-19.md\nDetected abrupt transition between scenes 2 and 3\nRecommended bridge paragraph length: 90-140 words"
        : undefined,
  }
}

export function genericTool(id: string, toolName: string, args: Record<string, unknown>): ToolItem {
  return {
    kind: "tool",
    id,
    toolName,
    status: "done",
    argsText: JSON.stringify(args, null, 2),
    parsedArgs: args,
    resultText: '{"status": "ok"}',
  }
}
