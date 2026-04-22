/**
 * ThreadScenarioBuilder — generates realistic AG-UI streaming event
 * timelines for Storybook demos.
 *
 * Three layers:
 *   1. Content pools (content-pools.ts) — curated fiction-writing content
 *   2. TurnBuilder — low-level primitives for one assistant turn
 *   3. ThreadScenarioBuilder — high-level API that sequences turns
 *
 * TurnBuilder tracks timing with a relative cursor. ThreadScenarioBuilder
 * converts relative delays to absolute `delayMs` values (cumulative from
 * start) since that's what TimelineEntry expects.
 */

import type { StreamEvent } from '../streaming/events'
import type { TimelineEntry } from '../streaming/types'
import {
  randomFrom,
  CHAPTER_PATHS,
  NOTE_PATHS,
  PROSE_SNIPPETS,
  PROSE_LINES,
  PROSE_REPLACEMENTS,
  SEARCH_QUERIES,
  WEB_SEARCH_QUERIES,
  BASH_COMMANDS,
  BASH_OUTPUTS,
  SEARCH_RESULTS,
  WEB_SEARCH_RESULTS,
  THINKING_FRAGMENTS,
  USER_MESSAGES,
  ASSISTANT_RESPONSES,
} from './content-pools'

// ═══════════════════════════════════════════════════════════════════
// Timing constants
// ═══════════════════════════════════════════════════════════════════

const TIMING = {
  betweenTurns: 500,
  thinkingDelta: 40,
  textDelta: 30,
  argsDelta: 30,
  toolExecutionMin: 400,
  toolExecutionMax: 800,
  betweenTools: 150,
  parallelStagger: 50,
  thinkingPause: 100,    // pause after thinking block ends
  textPause: 100,        // pause after text block ends
}

// ═══════════════════════════════════════════════════════════════════
// Text chunking
// ═══════════════════════════════════════════════════════════════════

/** Split text into ~4-6 word chunks on word boundaries. */
function chunkText(text: string, wordsPerChunk = 5): string[] {
  const words = text.split(' ')
  const chunks: string[] = []
  for (let i = 0; i < words.length; i += wordsPerChunk) {
    const slice = words.slice(i, i + wordsPerChunk)
    // Add trailing space except for last chunk
    const chunk = i + wordsPerChunk < words.length ? slice.join(' ') + ' ' : slice.join(' ')
    chunks.push(chunk)
  }
  return chunks
}

/** Split JSON string into ~30 char chunks for args streaming. */
function chunkJson(json: string, charsPerChunk = 30): string[] {
  const chunks: string[] = []
  for (let i = 0; i < json.length; i += charsPerChunk) {
    chunks.push(json.slice(i, i + charsPerChunk))
  }
  return chunks
}

// ═══════════════════════════════════════════════════════════════════
// ID generation
// ═══════════════════════════════════════════════════════════════════

class IdGenerator {
  private counters = { thinking: 0, message: 0, tool: 0, user: 0 }

  thinking(): string { return `t${++this.counters.thinking}` }
  message(): string { return `m${++this.counters.message}` }
  tool(): string { return `tc${++this.counters.tool}` }
  user(): string { return `user-${++this.counters.user}` }
}

// ═══════════════════════════════════════════════════════════════════
// Turn Builder (one assistant turn)
// ═══════════════════════════════════════════════════════════════════

type ToolSpec = {
  name: string
  args: Record<string, unknown>
  result: string
  isError?: boolean
}

/**
 * Builds the event sequence for a single assistant turn.
 *
 * Timing uses a cursor that tracks relative position within the turn.
 * Each `add(delay)` increments the cursor. The ThreadScenarioBuilder
 * adds these relative positions to its own absoluteTime.
 */
export class TurnBuilder {
  private events: Array<{ relativeDelay: number; event: StreamEvent }> = []
  private ids: IdGenerator
  private cursor = 0

  constructor(ids: IdGenerator) {
    this.ids = ids
  }

  private add(delay: number, event: StreamEvent) {
    this.cursor += delay
    this.events.push({ relativeDelay: this.cursor, event })
  }

  /** Add a thinking block. */
  thinking(text?: string): this {
    const content = text ?? randomFrom(THINKING_FRAGMENTS)
    const id = this.ids.thinking()
    this.add(TIMING.thinkingPause, { type: 'THINKING_START', thinkingId: id })
    this.add(0, { type: 'THINKING_TEXT_MESSAGE_START', thinkingId: id })
    for (const chunk of chunkText(content)) {
      this.add(TIMING.thinkingDelta, { type: 'THINKING_TEXT_MESSAGE_CONTENT', thinkingId: id, delta: chunk })
    }
    this.add(TIMING.thinkingPause, { type: 'THINKING_TEXT_MESSAGE_END', thinkingId: id })
    return this
  }

  /** Add a text/content block. */
  text(text?: string): this {
    const content = text ?? randomFrom(ASSISTANT_RESPONSES)
    const id = this.ids.message()
    this.add(TIMING.textPause, { type: 'TEXT_MESSAGE_START', messageId: id })
    for (const chunk of chunkText(content)) {
      this.add(TIMING.textDelta, { type: 'TEXT_MESSAGE_CONTENT', messageId: id, delta: chunk })
    }
    this.add(TIMING.textPause, { type: 'TEXT_MESSAGE_END', messageId: id })
    return this
  }

  /** Add a single tool call. */
  tool(name: string, args?: Record<string, unknown>, result?: string, isError?: boolean): this {
    const spec = this.resolveToolSpec(name, args, result, isError)
    this.addToolEvents(spec)
    return this
  }

  /** Add parallel tool calls (interleaved events). */
  parallelTools(tools: Array<{ name: string; args?: Record<string, unknown>; result?: string; isError?: boolean }>): this {
    const specs = tools.map(t => ({
      ...this.resolveToolSpec(t.name, t.args, t.result, t.isError),
      id: this.ids.tool(),
    }))

    // Start all tools with slight stagger
    for (const spec of specs) {
      this.add(TIMING.parallelStagger, { type: 'TOOL_CALL_START', toolCallId: spec.id, toolCallName: spec.name })
    }

    // Interleave args chunks round-robin
    const argsChunks = specs.map(spec => ({
      id: spec.id,
      chunks: chunkJson(JSON.stringify(spec.args)),
    }))
    const maxChunks = Math.max(...argsChunks.map(a => a.chunks.length))
    for (let i = 0; i < maxChunks; i++) {
      for (const ac of argsChunks) {
        if (i < ac.chunks.length) {
          this.add(TIMING.argsDelta, { type: 'TOOL_CALL_ARGS', toolCallId: ac.id, delta: ac.chunks[i] })
        }
      }
    }

    // End all
    for (const spec of specs) {
      this.add(TIMING.argsDelta, { type: 'TOOL_CALL_END', toolCallId: spec.id })
    }

    // Results arrive with varying delays
    for (const spec of specs) {
      const execDelay = TIMING.toolExecutionMin + Math.floor(Math.random() * (TIMING.toolExecutionMax - TIMING.toolExecutionMin))
      this.add(execDelay, { type: 'TOOL_CALL_RESULT', toolCallId: spec.id, content: spec.result, isError: spec.isError })
    }

    return this
  }

  /** Add N random tool calls using content from pools. */
  randomTools(count: number, options?: { parallel?: boolean }): this {
    const toolTypes = ['Read', 'Edit', 'doc_search', 'web_search', 'Bash']
    const selected = Array.from({ length: count }, () => randomFrom(toolTypes))

    if (options?.parallel) {
      const specs = selected.map(name => ({ name, ...this.randomToolData(name) }))
      this.parallelTools(specs)
    } else {
      for (const name of selected) {
        const data = this.randomToolData(name)
        this.tool(name, data.args, data.result)
      }
    }
    return this
  }

  /** Get the built events. */
  getEvents(): Array<{ relativeDelay: number; event: StreamEvent }> {
    return this.events
  }

  // ─── Private helpers ───────────────────────────────────────────

  private resolveToolSpec(name: string, args?: Record<string, unknown>, result?: string, isError?: boolean): ToolSpec {
    if (args && result !== undefined) {
      return { name, args, result, isError }
    }
    const data = this.randomToolData(name)
    return { name, args: args ?? data.args, result: result ?? data.result, isError }
  }

  private randomToolData(name: string): { args: Record<string, unknown>; result: string } {
    switch (name) {
      case 'Read':
        return { args: { file_path: randomFrom([...CHAPTER_PATHS, ...NOTE_PATHS]) }, result: randomFrom(PROSE_SNIPPETS) }
      case 'Edit':
      case 'EditDocument':
        return { args: { file_path: randomFrom(CHAPTER_PATHS), old_string: randomFrom(PROSE_LINES), new_string: randomFrom(PROSE_REPLACEMENTS) }, result: 'Edit applied successfully.' }
      case 'doc_search':
        return { args: { pattern: randomFrom(SEARCH_QUERIES), path: 'chapters/' }, result: randomFrom(SEARCH_RESULTS) }
      case 'web_search':
        return { args: { query: randomFrom(WEB_SEARCH_QUERIES) }, result: randomFrom(WEB_SEARCH_RESULTS) }
      case 'Bash':
        return { args: { command: randomFrom(BASH_COMMANDS) }, result: randomFrom(BASH_OUTPUTS) }
      default:
        return { args: { input: 'test' }, result: '{"status": "ok"}' }
    }
  }

  private addToolEvents(spec: ToolSpec): void {
    const id = this.ids.tool()
    const argsJson = JSON.stringify(spec.args)

    this.add(TIMING.betweenTools, { type: 'TOOL_CALL_START', toolCallId: id, toolCallName: spec.name })
    for (const chunk of chunkJson(argsJson)) {
      this.add(TIMING.argsDelta, { type: 'TOOL_CALL_ARGS', toolCallId: id, delta: chunk })
    }
    this.add(TIMING.argsDelta, { type: 'TOOL_CALL_END', toolCallId: id })
    const execDelay = TIMING.toolExecutionMin + Math.floor(Math.random() * (TIMING.toolExecutionMax - TIMING.toolExecutionMin))
    this.add(execDelay, { type: 'TOOL_CALL_RESULT', toolCallId: id, content: spec.result, isError: spec.isError })
  }
}

// ═══════════════════════════════════════════════════════════════════
// Thread Builder (sequences turns into a full timeline)
// ═══════════════════════════════════════════════════════════════════

/**
 * High-level builder that sequences user messages and assistant turns
 * into a complete `TimelineEntry[]` timeline with absolute delays.
 */
export class ThreadScenarioBuilder {
  private entries: TimelineEntry[] = []
  private ids = new IdGenerator()
  private absoluteTime = 0

  /** Add a user message turn. */
  user(text?: string): this {
    const content = text ?? randomFrom(USER_MESSAGES)
    this.absoluteTime += TIMING.betweenTurns
    // TODO: USER_MESSAGE is not yet in the StreamEvent union — add it when
    // we build the thread reducer. Cast the whole event until then.
    this.entries.push({
      delayMs: this.absoluteTime,
      event: { type: 'USER_MESSAGE', messageId: this.ids.user(), text: content } as unknown as StreamEvent,
    })
    return this
  }

  /** Add an assistant turn. */
  assistant(build: (turn: TurnBuilder) => void): this {
    const turn = new TurnBuilder(this.ids)
    build(turn)

    this.absoluteTime += TIMING.betweenTurns
    // RUN_STARTED
    this.entries.push({ delayMs: this.absoluteTime, event: { type: 'RUN_STARTED' } })

    // Add all turn events, converting relative delays to absolute
    for (const { relativeDelay, event } of turn.getEvents()) {
      if (relativeDelay > 0) {
        this.absoluteTime += relativeDelay
      }
      this.entries.push({ delayMs: this.absoluteTime, event })
    }

    // RUN_FINISHED
    this.absoluteTime += 200
    this.entries.push({ delayMs: this.absoluteTime, event: { type: 'RUN_FINISHED' } })

    return this
  }

  /** Build the final timeline. */
  build(): TimelineEntry[] {
    return [...this.entries]
  }
}
