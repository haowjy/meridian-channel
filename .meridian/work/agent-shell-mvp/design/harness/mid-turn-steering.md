# Mid-Turn Steering: The Stdin Control Protocol

> What this is: the differentiating-feature design — the stdin control
> protocol, the per-harness injection mechanics, the `meridian spawn
> inject` CLI primitive, and how all of that lives next to the
> existing meridian-channel spawn lifecycle without breaking it.
>
> What this is not: the AG-UI event taxonomy (lives in events/), or
> the per-harness wire format (lives in [`adapters.md`](adapters.md)).

Up: [`overview.md`](overview.md).

## Mid-Turn Steering Is Tier-1, Not A Footnote

Per [`../findings-harness-protocols.md`](../findings-harness-protocols.md)
**§ "Mid-Turn Steering is Tier-1, Not Optional"**, mid-turn injection
is **the differentiating feature of the platform** and the harness
abstraction must be shaped around it from day one. The findings doc is
explicit about why this isn't a "nice-to-have we might add in V1" —
retrofitting steering into a Claude-only abstraction means rebuilding
the interface, and the platform's value proposition collapses to "yet
another chat UI over Claude Code" without it.

The user-visible motivation: today's typical agent loop is **prompt →
wait minutes/hours → read report → respawn with corrections**. That's
slow and lossy. The platform we're refactoring meridian-channel to
support collapses the loop by making **every spawn in the tree
steerable mid-execution** — a user (or a parent orchestrator) can say
"wait, reconsider X" mid-run and the running agent absorbs the
correction without being killed and respawned. The
[findings doc](../findings-harness-protocols.md) is the authoritative
statement; this design implements it.

Two consequences for the design pass:

1. **Capability is a semantic enum, not a boolean.** The three
   harnesses really do behave differently mid-turn. Claude queues to
   the next safe boundary; Codex interrupts the current turn and
   restarts; OpenCode POSTs to a live session. Capability honesty is
   the principle — see [`abstraction.md`](abstraction.md).
2. **The control surface lives at every layer.** Adapter method,
   normalized control frame on the wire, CLI command, AG-UI capability
   event so the consumer can render the right affordance.

## Control Frame Model

Three frame types ride on the streaming spawn's stdin as **JSONL**.
Frames live in the new `harness/control_channel.py` sibling module;
each is a Pydantic model with a discriminated `type` field and a
`version` field for additive evolution.

```jsonl
{"version": "0.1", "type": "user_message", "id": "uuid", "text": "wait, reconsider X"}
{"version": "0.1", "type": "interrupt",    "id": "uuid"}
{"version": "0.1", "type": "cancel",       "id": "uuid"}
```

| Field | Required | Notes |
|---|---|---|
| `version` | yes | `"0.1"` for V0. Adapters reject frames with an unknown major version. |
| `type` | yes | One of `user_message`, `interrupt`, `cancel`. |
| `id` | yes | Caller-generated identifier. Echoed back in `CONTROL_RECEIVED` and `CONTROL_ERROR` AG-UI events so the injector can correlate. |
| `text` | `user_message` only | The mid-turn message body. UTF-8. |

`version` ships from day one (per D37 open question #2 — recommendation
adopted). It's cheaper to require a field that adapters mostly ignore
than to retrofit one when v0.2 needs to add an attachment field or a
streaming-text frame.

### Frame Semantics Across All Adapters

| Frame | What it means | What the adapter is required to do |
|---|---|---|
| `user_message` | "Deliver this user input to the running spawn." | Translate to the harness-native injection mechanism using the `mid_turn_injection` mode this adapter declares. Emit `CONTROL_RECEIVED` (or `CONTROL_ERROR`) on the AG-UI stream. |
| `interrupt` | "Stop the current turn but keep the spawn alive." | If `supports_interrupt`, signal the harness to stop the in-flight turn cleanly and emit `RUN_FINISHED` for that turn. If not, emit `CONTROL_ERROR` with a clear reason. |
| `cancel` | "Tear the whole spawn down." | Emit a final `RUN_FINISHED`, signal the harness subprocess (`SIGTERM` with timeout, then `SIGKILL`), close stdout, exit. Required of all adapters; `supports_cancel` defaults `True`. |

`interrupt` is intentionally distinct from `cancel`. A consumer that
wants "stop generating but let me reframe" sends `interrupt` and
follows up with `user_message`. A consumer that wants "kill this
spawn" sends `cancel`.

## Per-Harness Injection Mechanics

The adapter hides the wire mechanic; the consumer always sends the
same `user_message` frame. What happens inside:

### Claude Code — `mid_turn_injection = "queue"`

The adapter writes a stream-json `user` message frame to the harness
subprocess's stdin (the **harness's** stdin, not meridian's). Claude
queues the message and delivers it at the next safe turn boundary —
typically right after the current tool call settles or the current
text message ends.

User-visible semantics: **"Message will be applied at the next turn
boundary."** The frontend (or CLI) shows a queued indicator until the
adapter emits the corresponding `STEP_STARTED` for the new turn.

Claude is the lowest-friction case because the harness's own input
format is what the adapter writes, just at a different time than the
initial prompt.

### Codex (`codex app-server`) — `mid_turn_injection = "interrupt_restart"`

The adapter calls JSON-RPC `turn/interrupt` to stop the current turn,
then `turn/start` with the injected `user_message.text` as the new
turn's initial prompt. Per the
[findings doc](../findings-harness-protocols.md), this is the
documented stable mechanism — `turn/interrupt` is part of Codex's
core stable protocol over stdio.

User-visible semantics: **"This will interrupt the current turn."**
The frontend shows the interrupt warning before the injection actually
happens. The previous turn's `RUN_FINISHED` arrives before the new
turn's `STEP_STARTED`.

This is the case where **honesty** matters most — pretending Codex's
interrupt-restart is the same as Claude's queue-and-deliver would mean
silently destroying the current turn without telling the user. The
capability enum is what makes the difference visible.

### OpenCode — `mid_turn_injection = "http_post"`

The adapter holds a session URL (resolved at launch) and POSTs the
injected `user_message.text` to the live session's message endpoint.
The OpenCode session emits the resulting events on its own event
stream, which the adapter is already tailing for the AG-UI translation
path.

User-visible semantics: **normal send button**. POSTing to a live
session is conceptually the same as a fresh user message; OpenCode
handles the multi-turn-during-streaming case at the session layer.

Per the findings doc, this is the "cleanest of the three" because the
HTTP session API was explicitly designed for external drivers.

## Capability Reporting On The Wire

Every adapter emits a `CAPABILITY` AG-UI event **as the very first
event** on the spawn's AG-UI stream — before `RUN_STARTED`, before any
event the consumer might branch on:

```json
{
  "type": "CAPABILITY",
  "harness": "claude" | "codex" | "opencode",
  "capabilities": {
    "mid_turn_injection": "queue" | "interrupt_restart" | "http_post" | "none",
    "supports_interrupt": true,
    "supports_cancel": true,
    "supports_runtime_model_switch": false,
    "supports_cost_tracking": true,
    "supports_structured_reasoning_stream": true,
    "control_protocol_version": "0.1"
  }
}
```

The frontend uses this event to render the right affordance:

- `queue` → composer stays enabled mid-turn, with a "queued for next
  turn" hint
- `interrupt_restart` → composer stays enabled, with a "this will
  interrupt the current turn" warning before send
- `http_post` → composer stays enabled, normal send button
- `none` → composer disabled while a turn is in flight

The CLI consumer (e.g. a dev-workflow orchestrator forwarding
inject from a parent session) uses the same data to format human-
readable status messages.

`control_protocol_version` lets the consumer reject a streaming spawn
whose protocol it does not understand, the same way version-skewed
clients reject old REST APIs.

## Stdin Ownership And The Per-Spawn Control FIFO

**Open question D37 #1.** Does the streaming spawn own its own stdin
exclusively, or sit behind a per-spawn control FIFO?

**Recommendation: both, with ownership split by who is doing the
injecting.**

The collision is real: per [`../refactor-touchpoints.md`](../refactor-touchpoints.md)
and direct inspection of `src/meridian/lib/launch/process.py:116-149`,
the **primary launch path already copies parent stdin straight into
the child PTY**. A naïve "streaming spawn owns its stdin and reads
control frames from it" approach would either break interactive
`meridian` sessions or accidentally feed PTY input to the harness as
if it were a control frame. Both are unacceptable.

The split:

1. **Streaming-mode launch is a non-PTY launch flavor.** The
   streaming launch type in `harness/launch_types.py` declares "no
   PTY relay, no parent-stdin copy." `launch/process.py` learns one
   new branch: when streaming mode is requested, do not enter the
   PTY/stdin-relay path. Streaming spawns are designed for
   non-interactive callers (a Go backend, an orchestrator, an SDK
   client) — there is no terminal to relay.

2. **The streaming spawn's own stdin IS its primary control channel.**
   The streaming launch wires the meridian-channel process's stdin
   directly to the harness adapter's `ControlChannelReader`. A caller
   that pipes JSONL frames into `meridian spawn create --stream` is
   sending control frames; that's the contract, and it matches what
   meridian-flow's Go backend wants (subprocess with stdin/stdout
   JSONL — see [`../reframe.md`](../reframe.md)).

3. **`meridian spawn inject` writes to a per-spawn control FIFO**, not
   to the streaming spawn's stdin directly. The FIFO lives at:

   ```
   .meridian/spawns/<spawn_id>/control.fifo
   ```

   This is the only authoritative per-spawn anchor today (per the
   touchpoints map's structural analysis). The streaming spawn opens
   the FIFO read-only on launch and tees frames from **both** its own
   stdin and the FIFO into a single internal control queue. From the
   adapter's perspective, frames look the same regardless of which
   side they came from — both go through `ControlChannelReader`.

This split has two real benefits:

- **Decouples injector from spawner.** The process that started the
  streaming spawn is not necessarily the process that wants to inject.
  In dev-workflow use, an orchestrator spawns a `coder` agent and the
  user CLI is the injector. In meridian-flow use, the Go backend
  spawns and the same Go backend injects (so it could write to
  stdin), but a sibling CLI tool (or a future monitoring process)
  could also inject without holding the spawn's stdin handle.
- **Survives the case where the spawner is the streaming caller's
  stdin source.** A Go backend that pipes a control protocol over the
  spawn's stdin still gets to inject from a different goroutine or a
  different process via the FIFO.

The cost is one filesystem primitive (a named pipe), which is cheap on
Linux/macOS, well-supported by Python's `os.mkfifo`, and survives the
crash-only design discipline because the FIFO path is recorded in
`spawn_store.py` before the streaming spawn opens it. After a crash,
the orphan reaper detects a dangling FIFO the same way it detects
dangling pid files today.

### What Has To Change In State

`spawn_store.py` and `paths.py` learn one new piece of metadata: the
control surface descriptor for a streaming spawn. From the touchpoints
map: `state/spawn_store.py` has no live-control metadata today, and
`state/paths.py` has the per-spawn directory but no FIFO knowledge.

```python
# state/paths.py
def resolve_spawn_control_fifo(repo_root: Path, spawn_id: SpawnId) -> Path:
    return resolve_spawn_log_dir(repo_root, spawn_id) / "control.fifo"

# state/spawn_store.py  (new field on SpawnRecord)
control_protocol: Literal["none", "fifo+stdin"] = "none"
control_protocol_version: str | None = None
```

`reaper.py` learns to clean up dangling FIFOs the same way it cleans
up dangling pid files. Per the touchpoints map, the reaper is
sensitive — it treats `report.md` as a completion signal — so the
streaming-mode finalization path must continue producing `report.md`
exactly when it does today.

## `meridian spawn inject <spawn_id> "message"`

A new top-level CLI command in `cli/spawn.py`. Shape:

```bash
meridian spawn inject <spawn_id> "wait, reconsider X"
meridian spawn inject <spawn_id> --interrupt
meridian spawn inject <spawn_id> --cancel
meridian spawn inject <spawn_id> --frame-file frame.json
```

### Resolution

1. Resolve `<spawn_id>` against `state/spawn_store.py` (full id or
   prefix, the way `spawn show` already resolves).
2. Read the spawn record. Verify `control_protocol == "fifo+stdin"`
   (i.e. it was launched in streaming mode).
3. Resolve the FIFO path via `paths.resolve_spawn_control_fifo(...)`.

### Writing The Frame

4. Build a `ControlFrame` Pydantic model with a fresh `id`, the
   `version` from `control_protocol_version`, and the requested type.
5. Serialize to JSONL.
6. `open(fifo_path, 'wb')` and write the frame followed by a newline.
   Block on the open until the streaming spawn has its read side
   open (FIFO semantics handle this — the writer blocks on `open` if
   no reader is attached).

### Failure Modes

The CLI has two distinct failure surfaces:

| Failure | Detection | UX |
|---|---|---|
| `<spawn_id>` not found | `spawn_store.py` lookup | Synchronous error: "no such spawn" |
| Spawn not in streaming mode | `control_protocol == "none"` | Synchronous error: "spawn was not launched with --stream; injection is unavailable" |
| FIFO does not exist | `paths.resolve_spawn_control_fifo` + `os.path.exists` | Synchronous error: "control fifo missing — spawn may have crashed" |
| FIFO open blocks indefinitely (no reader) | configurable timeout, default 5s | Synchronous error: "spawn is not reading control frames — may have exited" |
| Frame written, but harness rejects it mid-turn | adapter emits `CONTROL_ERROR` AG-UI event | **Asynchronous** — the inject CLI succeeded; the consumer of the AG-UI stream sees the error |

This is the resolution to **D37 open question #3**: hybrid error
reporting. Synchronous failures from `meridian spawn inject` for
**delivery** errors (the frame couldn't be handed to the spawn).
Asynchronous `CONTROL_ERROR` AG-UI events for **adapter-level**
failures (the frame was delivered but the harness can't honor it
right now). The two surfaces line up with the two consumers: the CLI
caller wants exit codes, the AG-UI stream consumer wants events.

The recommendation: **error if not in streaming mode**, do not
fall back. Falling back to "open a one-shot subprocess and try to
inject" would silently violate the user's mental model — they ran
`spawn inject` against a non-streaming spawn and got something
unexpected. A clear error message tells them to relaunch with
`--stream`.

## Integration With Existing `spawn` Subcommands

**D37 open question #4.** Does streaming mode change `spawn wait`,
`spawn show`, `spawn log`?

**Recommendation: streaming is a parallel invocation shape, existing
inspection commands keep working unchanged.**

| Command | Behavior in streaming mode |
|---|---|
| `spawn create` | Gains a `--stream` flag (or equivalent — exact name a planning concern). Default behavior unchanged. |
| `spawn show <id>` | Unchanged. Reads `state/spawn_store.py` and the per-spawn artifact dir. Streaming spawns get an extra row showing `control_protocol` and the FIFO path. |
| `spawn log <id>` | Unchanged. Continues to read from `output.jsonl` and the assistant tail. The streaming AG-UI events are written to a sibling sink so the existing transcript display path is undisturbed. |
| `spawn wait <id>` | Unchanged. Waits on the same lifecycle signals (terminal status in `spawn_store.py`, `report.md` durability). Streaming spawns reach the same terminal states. |
| `spawn files <id>` | Unchanged. |
| `spawn stats` | Unchanged. |
| `spawn cancel <id>` | Existing path stays. For streaming spawns, this is equivalent to `spawn inject <id> --cancel` from the user's perspective; under the hood it can flow through the same control frame path or hit the existing kill plumbing — implementation discretion. |
| `spawn inject <id>` | **New.** Only valid when `control_protocol == "fifo+stdin"`. |

The principle: **streaming mode is a launch-time choice that
publishes a richer event stream and a control surface, but the
artifact contracts stay the same.** Every existing
inspection/recovery path keeps working because the artifact
directory is still where the truth lives.

## Capability Honesty Restated

The three injection modes are honestly different. The abstraction
unifies the **capability** ("send a `user_message` frame") and surfaces
the **semantics** (`queue` vs `interrupt_restart` vs `http_post`) so
the caller can render the right affordance and the user is not lied to
about wire-level behavior.

This is restated here because it's the principle that decides every
trade-off in the streaming control protocol. When in doubt, **expose
the difference, do not paper over it**.

## Open Questions Still Requiring User Input

The four D37 open questions are resolved above with explicit
recommendations. The remaining items the architect cannot resolve
unilaterally are:

1. **Exact CLI flag/subcommand name for streaming launch.** This doc
   uses `--stream`. The planner pass should pick the final spelling
   once the planner has the broader CLI ergonomics in view. Candidates:
   `meridian spawn create --stream`, `meridian spawn stream`,
   `meridian spawn open`. Recommendation: `--stream` for minimal
   surface area.
2. **Whether `spawn cancel <id>` should route through the control
   frame path for streaming spawns.** Tradeoff: routing through the
   control frame path is more uniform; keeping the existing kill
   plumbing is lower risk for the touchpoints map. Recommendation:
   keep existing kill plumbing for V0; revisit if user-visible cancel
   semantics drift.
3. **Whether `meridian spawn inject` should support a `--frame-file`
   path mode for batch injection or streaming control input.** Useful
   for orchestrators that already have a JSONL control stream;
   incremental cost is small. Recommendation: include from V0 — same
   command, two input modes (`--text` vs `--frame-file`), with
   `--text` as the default positional shorthand.
4. **What `interrupt` should look like on harnesses that don't have a
   native interrupt primitive.** For Codex, `interrupt` maps directly
   to `turn/interrupt`. For OpenCode, the session API may or may not
   expose a `cancel current turn` endpoint; if not, the V0 OpenCode
   adapter declares `supports_interrupt = False` and rejects the
   frame with `CONTROL_ERROR`. For Claude in queue mode, "interrupt"
   has no clean primitive — Claude completes its current turn and
   then queues stop. The honest answer is `supports_interrupt =
   False` for Claude V0; revisit if a real primitive emerges.

## Read Next

- [`abstraction.md`](abstraction.md) — the adapter interface that
  hosts the new methods
- [`adapters.md`](adapters.md) — per-harness wire format and
  per-tool render config
- [`../events/flow.md`](../events/flow.md) — the AG-UI event sequence
  the streaming spawn produces, including where `CAPABILITY`,
  `CONTROL_RECEIVED`, and `CONTROL_ERROR` fit in
- [`../refactor-touchpoints.md`](../refactor-touchpoints.md) — the
  per-file map of what changes to enable this protocol
