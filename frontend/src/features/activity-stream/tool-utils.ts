import {
  BookOpen,
  Globe,
  MagnifyingGlass,
  PencilSimple,
  Robot,
  Terminal,
} from "@phosphor-icons/react"

import type { BadgeProps } from "@/components/ui/badge"

import type { ActivityItem, ToolItem, ToolStatus } from "./types"

// ═══════════════════════════════════════════════════════════════════
// Tool categories — inferred from toolName string
// ═══════════════════════════════════════════════════════════════════

export type ToolCategory = "read" | "edit" | "doc-search" | "web-search" | "bash" | "agent" | "other"

/**
 * Split a tool name into word-boundary segments.
 * Handles camelCase, snake_case, kebab-case, and spaces.
 *   "ReadFile"      → ["read", "file"]
 *   "str_replace"   → ["str", "replace"]
 *   "web-search"    → ["web", "search"]
 *   "SpawnAgent"    → ["spawn", "agent"]
 *   "thread"        → ["thread"]
 */
function extractSegments(name: string): string[] {
  return name
    .replace(/([a-z])([A-Z])/g, "$1_$2")
    .toLowerCase()
    .split(/[_\-\s]+/)
    .filter(Boolean)
}

/** True if any candidate appears as an exact segment. */
function hasSegment(segments: string[], candidates: string[]): boolean {
  return candidates.some((c) => segments.includes(c))
}

/** Classify a tool by name. Works with any naming convention (Claude, MCP, custom). */
export function getToolCategory(toolName: string): ToolCategory {
  const segments = extractSegments(toolName.trim())

  if (hasSegment(segments, ["read", "view", "open"])) {
    return "read"
  }

  if (hasSegment(segments, ["edit", "write", "replace", "patch", "overwrite"])) {
    return "edit"
  }

  // web-search before doc-search so "web_search" doesn't match generic "search" first
  if (segments.includes("web") && segments.includes("search")) {
    return "web-search"
  }

  if (hasSegment(segments, ["search", "grep", "glob", "find"])) {
    return "doc-search"
  }

  if (hasSegment(segments, ["bash", "terminal", "command", "exec", "execute"])) {
    return "bash"
  }

  if (hasSegment(segments, ["agent", "spawn", "delegate", "thread"])) {
    return "agent"
  }

  return "other"
}

// ═══════════════════════════════════════════════════════════════════
// Icons
// ═══════════════════════════════════════════════════════════════════

export function getToolIcon(category: ToolCategory) {
  if (category === "read") {
    return BookOpen
  }

  if (category === "edit") {
    return PencilSimple
  }

  if (category === "doc-search") {
    return MagnifyingGlass
  }

  if (category === "web-search") {
    return Globe
  }

  if (category === "agent") {
    return Robot
  }

  return Terminal
}

// ═══════════════════════════════════════════════════════════════════
// Labels
// ═══════════════════════════════════════════════════════════════════

/** Human label for the tool category. "Tool" if unknown. */
export function getToolLabel(toolName?: string): string {
  if (!toolName) {
    return "Tool"
  }

  const category = getToolCategory(toolName)

  if (category === "read") return "Read"
  if (category === "edit") return "Edit"
  if (category === "doc-search") return "Search"
  if (category === "web-search") return "Web"
  if (category === "bash") return "Bash"
  if (category === "agent") return "Agent"

  return "Tool"
}

// ═══════════════════════════════════════════════════════════════════
// Progressive summary extraction
//
// Works with partial data — called on every TOOL_CALL_ARGS delta.
// Returns whatever summary text is available so far.
// ═══════════════════════════════════════════════════════════════════

/** Read the first matching string value from an object. */
export function readString(obj: Record<string, unknown>, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = obj[key]

    if (typeof value === "string" && value.length > 0) {
      return value
    }
  }

  return undefined
}

/** Return the first string value found in a flat object. */
function firstStringValue(obj: Record<string, unknown>): string | undefined {
  for (const value of Object.values(obj)) {
    if (typeof value === "string" && value.length > 0) {
      return value
    }
  }

  return undefined
}

/**
 * Extract a display summary from tool args. Streams progressively —
 * returns partial results as parsedArgs builds up from partial-json.
 *
 * Read: file path         → Read("src/components/Button.tsx")
 * Edit: file path         → Edit("src/lib/utils.ts")
 * Bash: command           → Bash("ls -la src/")
 * Search: pattern/query   → Search("getUser")
 * Agent: name/prompt      → Agent("Continuity Scout")
 * Unknown: first string   → Tool("some value")
 */
export function getToolSummary(
  toolName: string | undefined,
  parsedArgs?: Record<string, unknown>,
  /** Pre-computed category to avoid redundant getToolCategory calls. */
  precomputedCategory?: ToolCategory,
): string | undefined {
  if (!parsedArgs) {
    return undefined
  }

  const category = precomputedCategory ?? getToolCategory(toolName ?? "")

  if (category === "read" || category === "edit") {
    const path = readString(parsedArgs, ["file_path", "path", "filePath", "target"])
    return path ? `"${path}"` : undefined
  }

  if (category === "bash") {
    return readString(parsedArgs, ["command", "cmd"])
  }

  if (category === "doc-search") {
    const query = readString(parsedArgs, ["pattern", "query", "search", "regex"])
    return query ? `"${query}"` : undefined
  }

  if (category === "web-search") {
    const query = readString(parsedArgs, ["query", "search_query", "q"])
    return query ? `"${query}"` : undefined
  }

  if (category === "agent") {
    return readString(parsedArgs, ["name", "description", "prompt", "task"])
  }

  // Generic: first string value
  return firstStringValue(parsedArgs)
}

/**
 * Full header title for a tool line: Label(summary)
 *
 * Streams progressively:
 *   "Tool"  →  "Read"  →  "Read(src/c)"  →  "Read(src/components/Button.tsx)"
 */
export function getToolLineTitle(tool: ToolItem, precomputedCategory?: ToolCategory): string {
  const category = precomputedCategory ?? getToolCategory(tool.toolName ?? "")
  const label = getToolLabel(tool.toolName)
  const summary = getToolSummary(tool.toolName, tool.parsedArgs, category)

  if (!summary) {
    return label
  }

  return `${label}(${summary})`
}

// ═══════════════════════════════════════════════════════════════════
// Status display
// ═══════════════════════════════════════════════════════════════════

export function getToolStatusLabel(status: ToolStatus): string {
  if (status === "done") return "ok"
  if (status === "error") return "error"
  if (status === "executing") return "running"
  if (status === "streaming-args") return "streaming"

  return "pending"
}

export function getToolStatusVariant(status: ToolStatus): BadgeProps["variant"] {
  if (status === "done") return "success"
  if (status === "error") return "destructive"
  if (status === "executing") return "secondary"
  if (status === "streaming-args") return "outline"

  return "outline"
}

// ═══════════════════════════════════════════════════════════════════
// Activity-level summaries
// ═══════════════════════════════════════════════════════════════════

export const STREAMING_STATUS_MESSAGES = [
  "Turning pages...",
  "Consulting the muse...",
  "Reading between the lines...",
  "Sharpening the quill...",
  "Pondering the plot...",
  "Checking the manuscript...",
  "Weighing the words...",
  "Following the thread...",
]

function pluralize(count: number, singular: string, plural: string) {
  return count === 1 ? singular : plural
}

export function getActivitySummary(items: ActivityItem[]) {
  const counts: Record<ToolCategory, number> = {
    "read": 0,
    "edit": 0,
    "doc-search": 0,
    "web-search": 0,
    "bash": 0,
    "agent": 0,
    "other": 0,
  }

  for (const item of items) {
    if (item.kind !== "tool") {
      continue
    }

    counts[getToolCategory(item.toolName ?? "")] += 1
  }

  const parts: string[] = []

  if (counts.read > 0) {
    parts.push(`read ${counts.read} ${pluralize(counts.read, "file", "files")}`)
  }

  if (counts.edit > 0) {
    parts.push(`edited ${counts.edit}`)
  }

  if (counts["doc-search"] > 0) {
    parts.push(`searched ${counts["doc-search"]}`)
  }

  if (counts["web-search"] > 0) {
    parts.push(`web searched ${counts["web-search"]}`)
  }

  if (counts.bash > 0) {
    parts.push(`ran ${counts.bash} ${pluralize(counts.bash, "command", "commands")}`)
  }

  if (counts.agent > 0) {
    parts.push(`spawned ${counts.agent} ${pluralize(counts.agent, "agent", "agents")}`)
  }

  if (parts.length === 0) {
    return "thinking..."
  }

  return parts.join(", ")
}
