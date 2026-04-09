# Per-Harness Adapters

> What this is: per-harness translation rules — wire format today,
> AG-UI mapping summary, per-tool render config, regression risks.
>
> What this is not: the full per-field harness → AG-UI mapping table.
> That lives in [`../events/harness-translation.md`](../events/harness-translation.md)
> (Architect B). This doc points at it; do not duplicate it.

Up: [`overview.md`](overview.md).

## All Three Are Tier-1

Per [`../findings-harness-protocols.md`](../findings-harness-protocols.md),
**Claude Code, Codex app-server, and OpenCode are all tier-1** design
targets with stable, programmatic, mid-turn-capable control surfaces.
Earlier framing that treated Codex as experimental or deferred is
wrong and is corrected throughout this doc and
[`mid-turn-steering.md`](mid-turn-steering.md).

Implementation order is a product decision, not a protocol decision.
The abstraction has to fit all three from day one.

## Claude Code

### Wire Protocol Today

Claude Code runs as a subprocess driven by `--input-format stream-json
--output-format stream-json`, exchanging NDJSON frames over
stdin/stdout. The current `claude.py` adapter builds the command,
captures stdout into `output.jsonl`, runs `extract_report` /
`extract_session_id` / `extract_usage` against the captured artifacts
on completion, and returns a `SpawnResult`. Claude streams thinking,
text, and tool use as separate JSON message families, plus tool result
frames flow back in via the same stream.

Per-line frame families relevant to AG-UI translation:

- `system` boot/handshake frames — translate to `RUN_STARTED` plus the
  `CAPABILITY` event
- `assistant` message frames with content blocks (`text`, `thinking`,
  `tool_use`) — translate to `TEXT_MESSAGE_*`, `THINKING_*`,
  `TOOL_CALL_*`
- `user` message frames with `tool_result` content blocks — translate
  to `TOOL_CALL_RESULT` and `TOOL_OUTPUT`
- `result` summary frame — `RUN_FINISHED`

### AG-UI Translation Summary

| Claude wire | AG-UI event |
|---|---|
| `system` boot | `RUN_STARTED` + `CAPABILITY` |
| `assistant` text content | `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END` |
| `assistant` thinking content | `THINKING_START` / `THINKING_TEXT_MESSAGE_CONTENT` |
| `assistant` `tool_use` block | `TOOL_CALL_START` (with per-tool render config) + `TOOL_CALL_ARGS` |
| Tool start/finish boundary | `TOOL_CALL_END` |
| `user` `tool_result` content | `TOOL_CALL_RESULT` + `TOOL_OUTPUT` |
| `result` summary | `RUN_FINISHED` (with token usage) |

The full per-field mapping (which Claude attribute fills which AG-UI
field, how streaming text deltas frame `TEXT_MESSAGE_CONTENT`, how
`tool_use` argument streaming maps to incremental `TOOL_CALL_ARGS`)
lives in [`../events/harness-translation.md`](../events/harness-translation.md).

Claude is the only tier-1 harness that exposes a structured reasoning
stream today, so `capabilities.supports_structured_reasoning_stream =
True`.

### Per-Tool Render Config

Claude's tool set is the standard Anthropic harness tool set plus
whatever MCP tools are configured for the run. Default render config
for the built-in tools matches what meridian-flow's reducer already
expects. The canonical examples live in meridian-flow:

- [`meridian-flow/.meridian/work/biomedical-mvp/design/backend/bash-tool.md`](../../../../../meridian-flow/.meridian/work/biomedical-mvp/design/backend/bash-tool.md)
  — bash: input collapsed, stdout collapsed
- [`meridian-flow/.meridian/work/biomedical-mvp/design/backend/python-tool.md`](../../../../../meridian-flow/.meridian/work/biomedical-mvp/design/backend/python-tool.md)
  — python: input collapsed, stdout **inline / visible**

For the Claude built-ins (and the matching MCP tool defaults), the
adapter ships these render defaults on `TOOL_CALL_START`:

| Tool | Input | Output |
|---|---|---|
| `Bash` | collapsed | collapsed |
| `Read` | collapsed | collapsed |
| `Grep` | collapsed | collapsed |
| `Glob` | collapsed | collapsed |
| `Edit`, `Write`, `MultiEdit` | collapsed | collapsed |
| `WebFetch`, `WebSearch` | collapsed | collapsed |
| `Task` (sub-agent) | visible (one line) | collapsed |
| MCP tool: `python` | collapsed | inline |
| MCP tool: any other | collapsed | collapsed |

These defaults are not invented here — they reproduce what
meridian-flow's reducer already applies for the cloud path. The
adapter's job is to attach the right config to the right
`TOOL_CALL_START` event so the reducer does not have to special-case
the local-deployment path.

### Report / Session Compatibility

The Claude adapter must keep producing every artifact the existing
dogfood workflow depends on:

- `report.md` — produced by Claude itself or extracted from the
  assistant tail per the existing fallback chain (`launch/report.py`,
  `extract_report`).
- `output.jsonl` — the existing raw JSONL capture path stays. AG-UI
  events are written to a **separate sink** (the spawn's stdout in
  `--stream` mode, or a sibling artifact file in non-streaming mode).
- `stderr.log` — unchanged. `ops/spawn/query.py` reads it for the
  running-spawn last-assistant snippet that drives `--from`.
- Session id extraction — unchanged. `extract_session_id`,
  `resolve_session_file`, `detect_primary_session_id` continue against
  Claude's session file shape.
- `--continue` / `--continue --fork` — unchanged. The streaming-mode
  launch flavor inherits the existing session-resume path.

**Regression risks specific to Claude:**

- `tests/harness/test_extraction.py` exercises the report fallback,
  written-files extraction, and usage extraction against synthetic
  Claude output. Any change to how `output.jsonl` is written must
  keep those test fixtures parseable.
- `tests/exec/test_claude_*` (per the touchpoints map) covers
  Claude-specific lifecycle behavior. The streaming-mode launch
  flavor must not change finalization order, signal handling, or
  report-watchdog timing.
- `launch/process.py` already copies parent stdin to the child PTY
  for primary launches. Streaming mode must take a separate launch
  path that does **not** PTY-relay parent stdin — see
  [`mid-turn-steering.md`](mid-turn-steering.md).

## Codex (`codex app-server`)

### Wire Protocol Today

Codex runs as `codex app-server` (or `codex exec --json` for the
existing meridian-channel `codex.py` adapter), exchanging
**JSON-RPC 2.0** over stdio. Per the findings doc, the **core
protocol is stable**: `initialize`/`initialized` handshake,
`thread/start`, `thread/resume`, `turn/start`, `turn/interrupt`, plus
`item/*` notifications for streaming output. WebSocket transport is
the experimental part; meridian-channel uses stdio, which is stable.

The `item/*` notifications cover the same conceptual surface as
Claude's stream-json, just framed differently:

- `item/agentMessage` — assistant text / final response
- `item/commandExecution` — tool call lifecycle for shell-style tools
- `item/fileChange` — tool call lifecycle for edit-style tools
- `item/reasoning` — thinking content (bulk-only in companion's
  reference adapter; streaming reasoning is a known gap)
- `item/webSearch`, `item/mcpToolCall` — additional tool families
- `item/contextCompaction` — context-window management notifications
- `item/*/requestApproval` — approval gate requests (server responds
  with decision)

### AG-UI Translation Summary

| Codex wire | AG-UI event |
|---|---|
| `initialized` | `RUN_STARTED` + `CAPABILITY` |
| `item/agentMessage` (text deltas) | `TEXT_MESSAGE_START` / `_CONTENT` / `_END` |
| `item/reasoning` (bulk) | `THINKING_START` + a single `THINKING_TEXT_MESSAGE_CONTENT` |
| `item/commandExecution` start | `TOOL_CALL_START` (bash render config) + `TOOL_CALL_ARGS` |
| `item/commandExecution` output stream | `TOOL_OUTPUT` (stream: stdout/stderr) |
| `item/commandExecution` complete | `TOOL_CALL_END` + `TOOL_CALL_RESULT` |
| `item/fileChange` lifecycle | `TOOL_CALL_START` (edit render config) + `TOOL_CALL_END` + `TOOL_CALL_RESULT` |
| `item/webSearch`, `item/mcpToolCall` | `TOOL_CALL_*` + render defaults per tool family |
| `item/contextCompaction` | (internal — no AG-UI event in V0; logged for diagnostics) |
| `turn/completed` | `RUN_FINISHED` |

The detailed per-field translation (the JSON-RPC envelope, the item
type discriminators, how `turn/completed` is decoded for token usage
when present) lives in
[`../events/harness-translation.md`](../events/harness-translation.md).
**Companion's [`web/CODEX_MAPPING.md`](https://github.com/The-Vibe-Company/companion)
is the best available reference** for this translation — read it,
reimplement in Python against our own AG-UI model, do not vendor.

Known capability gaps from companion's reference adapter (per the
findings doc) the V0 Codex adapter inherits and declares honestly:

- `supports_structured_reasoning_stream = False` (companion handles
  reasoning bulk-only; `item/reasoning/delta` is a follow-up)
- `supports_runtime_model_switch = False` (Codex sets the model at
  `thread/start` — runtime switching is not in the protocol)
- `supports_cost_tracking` — declare honestly. Companion does not
  surface per-token usage from `turn/completed` yet, but the field is
  there in the protocol; V0 Codex adapter declares whatever the first
  implementation actually wires up.

### Per-Tool Render Config

Codex's tool families map onto the same render-config buckets:

| Codex item type | Render config |
|---|---|
| `commandExecution` (shell) | input collapsed, stdout collapsed |
| `fileChange` | input collapsed, output collapsed |
| `webSearch` | input collapsed, results collapsed |
| `mcpToolCall` (python-style) | input collapsed, stdout inline |
| `mcpToolCall` (other) | input collapsed, output collapsed |

The render defaults are the same as the Claude built-in equivalents
because the consumer (meridian-flow's reducer) is the same. The
adapter's job is to attach the right per-tool config to each
`TOOL_CALL_START` based on the Codex item type.

### Report / Session Compatibility

The Codex adapter must keep producing every artifact the existing
dogfood workflow depends on. The touchpoints map flags Codex as one
of the highest-risk adapters because command construction, fork
materialization, and session extraction are all coupled in `codex.py`
today:

- `report.md` — extracted from the agent's tail per the existing
  fallback chain. The streaming AG-UI path must not change when or how
  `report.md` becomes durable, because `state/reaper.py` treats
  `report.md` as a completion signal.
- `output.jsonl` — unchanged. The raw JSON-RPC frames continue to be
  written; AG-UI translation is teed off the same line stream and
  written to the AG-UI sink separately.
- Session fork (`continue_fork`) — `tests/test_launch_process.py`
  exercises Codex fork materialization. The streaming launch flavor
  must not break this path.
- Session-id extraction from `extract_session_id` and
  `resolve_session_file` — unchanged.

**Regression risks specific to Codex:**

- `tests/test_launch_process.py` covers Codex fork materialization
  and PTY winsize forwarding.
- `tests/harness/test_extraction.py` exercises Codex output
  extraction.
- The JSON-RPC framing is line-oriented but each frame can be larger
  than typical Claude frames. `launch/stream_capture.py` already
  handles large lines and redaction; the AG-UI translator must not
  introduce a new line-size assumption.

## OpenCode

### Wire Protocol Today

OpenCode is driven via the **HTTP session API** exposed by `opencode
serve` (also ACP NDJSON for some flows). The current `opencode.py`
adapter builds a launch command, captures session events to log files,
and resolves session ownership from those files. Per the findings doc,
this is the **cleanest of the three** wire protocols — session-scoped,
designed explicitly to be driven by external tools.

Mid-turn injection on OpenCode is a `POST` to the live session's
message endpoint. No interrupt, no queue, no stream-format negotiation.

### AG-UI Translation Summary

| OpenCode session event | AG-UI event |
|---|---|
| Session start | `RUN_STARTED` + `CAPABILITY` |
| Assistant text delta | `TEXT_MESSAGE_START` / `_CONTENT` / `_END` |
| Tool invocation start | `TOOL_CALL_START` (with per-tool render config) + `TOOL_CALL_ARGS` |
| Tool invocation output | `TOOL_OUTPUT` |
| Tool invocation complete | `TOOL_CALL_END` + `TOOL_CALL_RESULT` |
| Session done | `RUN_FINISHED` |

OpenCode's reasoning surface is harness-dependent on the underlying
model; the adapter declares
`supports_structured_reasoning_stream` based on what the wired model
actually returns. Default `False` in V0.

Per-field mapping lives in
[`../events/harness-translation.md`](../events/harness-translation.md).

### Per-Tool Render Config

OpenCode's built-in tools cover the same surface as Claude's. Defaults
match the Claude/Codex tables above:

| Tool family | Input | Output |
|---|---|---|
| Shell / bash | collapsed | collapsed |
| Read / search / glob | collapsed | collapsed |
| Edit / write | collapsed | collapsed |
| Python (MCP) | collapsed | inline |
| Other MCP | collapsed | collapsed |

### Report / Session Compatibility

OpenCode's existing extraction paths in `opencode.py` and
`tests/ops/test_session_log.py` depend on the current session log
file shapes. The refactor must:

- Continue producing the same `report.md`, `output.jsonl`,
  `stderr.log` artifacts — AG-UI is additive, not a replacement.
- Continue resolving session ownership from log files (the
  `owns_untracked_session` path).
- Not regress the compaction-aware session log parser
  (`ops/session_log.py`) that exposes `meridian session log`.

**Regression risks specific to OpenCode:**

- `tests/ops/test_session_log.py` is the main regression boundary. If
  OpenCode session log files change shape because the refactor moves
  durable event capture into a new format, the compaction parser
  needs an update in lockstep.
- `tests/harness/test_extraction.py` exercises OpenCode output
  extraction.
- HTTP injection means the OpenCode `ControlDispatcher` needs an HTTP
  client and the live session URL — plumbing the URL through to the
  control reader is an OpenCode-specific concern that the other two
  adapters do not have.

## Summary Of Regression Surfaces (All Three)

The dogfood workflow depends on artifacts and behaviors that
**must not regress** for any adapter. From the touchpoints map:

| Surface | Owned by | Risk |
|---|---|---|
| `report.md` durability + content | `launch/extract.py`, `launch/report.py`, adapter `extract_report` | reaper treats `report.md` as completion signal |
| `output.jsonl` content | `launch/stream_capture.py`, `launch/runner.py` | `spawn log`, `--from`, transcript parsers all read it |
| `stderr.log` content | `launch/runner.py` | `ops/spawn/query.py` reads running-spawn assistant tail |
| Session id extraction | adapter `extract_session_id`, `detect_primary_session_id` | `--continue`, session ownership, `meridian session log` |
| Session fork (Codex) | adapter `fork_session`, `seed_session` | `tests/test_launch_process.py` |
| Per-spawn artifact directory | `state/paths.py` | every existing inspection command |
| Token usage extraction | adapter `extract_usage` | `meridian spawn stats`, dashboards |
| Reaper liveness | `state/reaper.py` | orphan detection on crash |

The refactor adds AG-UI events on top of these — it does not move them.
The implementation discipline is: **AG-UI sink first, every existing
artifact contract second**, and the existing artifact contracts win
when the two pull in different directions.

## Read Next

- [`mid-turn-steering.md`](mid-turn-steering.md) — the per-harness
  injection mechanics and the stdin control protocol in detail.
- [`../events/harness-translation.md`](../events/harness-translation.md)
  — the per-field mapping tables this doc references.
- [`../refactor-touchpoints.md`](../refactor-touchpoints.md) — the
  per-file impact map and the regression test/smoke surface.
