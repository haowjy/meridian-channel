# Harness Adapter Abstraction

> What this is: the target shape of the meridian-channel harness
> adapter interface after the D36/D37 refactor.
>
> What this is not: the AG-UI event schema (lives in
> [`../events/`](../events/) and ultimately in meridian-flow), or the
> per-harness translation rules (lives in [`adapters.md`](adapters.md)).

Up: [`overview.md`](overview.md).

## Three New Adapter Responsibilities

Today's `SubprocessHarness` protocol in `src/meridian/lib/harness/adapter.py`
covers command building, env setup, and post-hoc artifact extraction.
The refactor adds three orthogonal responsibilities:

1. **Emit AG-UI events on an output channel** — translate this harness's
   wire format into the canonical AG-UI event taxonomy and push events
   onto the spawn's stdout AG-UI channel **as they happen**, not after
   the run completes.
2. **Accept stdin control frames** — read normalized control frames
   (`user_message`, `interrupt`, `cancel`) from a per-spawn control
   surface and dispatch them through the harness-native injection
   mechanic.
3. **Report capabilities honestly** — extend `HarnessCapabilities` so
   the consumer (CLI, frontend, dev-workflow orchestrator) can render
   the right affordance for what this harness can actually do
   mid-turn.

These three responsibilities sit alongside the existing ones, not on
top of them. The existing artifact contracts (`report.md`,
`output.jsonl`, `stderr.log`, session-id extraction, `extract_usage`,
`extract_report`) keep working unchanged — that is what the existing
dogfood workflow depends on.

## Existing Surface That Stays

| Today (in `adapter.py`) | Refactor disposition |
|---|---|
| `class HarnessCapabilities(BaseModel)` | **extends** — adds `mid_turn_injection` and a few honesty flags |
| `class RunPromptPolicy(BaseModel)` | unchanged |
| `class SpawnParams(BaseModel)` | unchanged (streaming mode signaled via launch metadata, not by mutating SpawnParams) |
| `class McpConfig(BaseModel)` | unchanged |
| `class StreamEvent(BaseModel)` | unchanged — kept as the **internal** parsed-line type used by `launch/stream_capture.py`. AG-UI events are a separate model. |
| `class SpawnResult(BaseModel)` | unchanged |
| `class SubprocessHarness(Protocol)` (and `BaseSubprocessHarness`) | **extends** — adds AG-UI emission method, control-frame dispatch method, capability surface |
| `class InProcessHarness(Protocol)` | unchanged. `direct.py` keeps `supports_stream_events=False` and is **out of scope** for this refactor. |
| `class ConversationExtractingHarness(Protocol)` | unchanged |
| `class ArtifactStore(Protocol)`, `class PermissionResolver(Protocol)` | unchanged |
| `def resolve_mcp_config(...)` | unchanged |

The interface is grown, not replaced. Every existing call site
(`launch/runner.py`, `launch/process.py`, `ops/spawn/execute.py`, the
test suite) continues to work against the unchanged half of the
protocol.

## New Surface

### Event emission

AG-UI emission happens **inside the adapter**, not in a post-hoc layer.
The shared model + emitter live in a new sibling module:

```
src/meridian/lib/harness/ag_ui_events.py
```

`ag_ui_events.py` owns:

- The AG-UI event Pydantic models (one per event type — `RUN_STARTED`,
  `STEP_STARTED`, `THINKING_*`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`,
  `TOOL_OUTPUT`, `TOOL_CALL_RESULT`, `DISPLAY_RESULT`, `RUN_FINISHED`,
  plus the meridian-channel-specific `CAPABILITY` and `CONTROL_ERROR`
  events introduced in [`mid-turn-steering.md`](mid-turn-steering.md)).
- A small `AgUiEmitter` interface that adapters call into:
  `emit(event: AgUiEvent)`. The concrete emitter writes JSONL to the
  spawn's AG-UI sink (stdout in `--stream` mode, a per-spawn artifact
  file in non-streaming mode for replay).
- The **per-tool behavior config model** — a typed structure that
  attaches render defaults (input collapsed/visible, stdout
  visible/collapsed/inline) to a `TOOL_CALL_START` event. The set of
  fields matches what meridian-flow's frontend reducer already
  consumes — see [`adapters.md`](adapters.md) for the per-harness
  defaults and the meridian-flow tool docs for the canonical field
  list.

> **Reference, do not duplicate.** `ag_ui_events.py` defines a Python
> type model that **mirrors** the AG-UI taxonomy from
> [`meridian-flow/.meridian/work/biomedical-mvp/design/streaming-walkthrough.md`](../../../../../meridian-flow/.meridian/work/biomedical-mvp/design/streaming-walkthrough.md).
> When that taxonomy gains a field, the Python model gains a field. The
> taxonomy itself is **not** redefined here.

The adapter's responsibility is translation, not invention. Each
adapter reads its harness's wire frames and calls
`emitter.emit(...)` with the corresponding AG-UI event. The
translation rules per harness live in
[`../events/harness-translation.md`](../events/harness-translation.md)
(written by Architect B).

The new method on `SubprocessHarness` is roughly:

```python
async def stream_ag_ui_events(
    self,
    *,
    raw_lines: AsyncIterator[str],   # already framed by stream_capture
    emitter: AgUiEmitter,
    spawn_id: SpawnId,
) -> SpawnResult:
    """Translate harness wire frames into AG-UI events.

    Adapters override; the base class is a no-op for backward compat.
    """
```

The exact signature is a planning concern; the architectural commitment
is "translation runs **inside the adapter**, against an emitter the
harness layer hands in." The `launch/stream_capture.py` bridge already
has a generic event-observer callback hook (per the touchpoints map);
that hook is where the per-line stream is teed into the adapter's
translator.

### Stdin control surface

The control frame model + reader live in a second new sibling module:

```
src/meridian/lib/harness/control_channel.py
```

`control_channel.py` owns:

- The `ControlFrame` Pydantic model and its three concrete subtypes
  (`UserMessageFrame`, `InterruptFrame`, `CancelFrame`). Field shapes
  and the `version` field are pinned in
  [`mid-turn-steering.md`](mid-turn-steering.md).
- A `ControlChannelReader` that reads JSONL frames from a file-like
  source (the per-spawn control FIFO described in
  `mid-turn-steering.md`), validates them, and yields typed frames.
- A `ControlDispatcher` interface adapters implement: a single
  `dispatch(frame: ControlFrame) -> None` (or async equivalent) that
  the harness reader calls when a new frame arrives. The dispatcher
  owns the harness-native translation: stream-json frame for Claude,
  `turn/interrupt` + `turn/start` for Codex, HTTP POST for OpenCode.

The shared piece is the **frame format and validation** — the same
JSONL shape on the wire, the same parser, the same version field. The
adapter-specific piece is the dispatcher implementation. This split is
deliberate per the touchpoints map: the three harnesses have different
runtime semantics for the same control frame, so the dispatch cannot
sit in `common.py`, but the parse-and-validate path absolutely should
be shared.

### Capability surface

`HarnessCapabilities` (in `adapter.py` today) gains a small set of
honesty fields:

```python
class HarnessCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    # ... existing fields stay ...
    supports_stream_events: bool = True
    supports_stdin_prompt: bool = False
    supports_session_resume: bool = False
    supports_session_fork: bool = False
    supports_native_skills: bool = False
    supports_native_agents: bool = False
    supports_programmatic_tools: bool = False
    supports_primary_launch: bool = False
    reference_input_mode: Literal["inline", "paths"] = "paths"

    # NEW — D37/findings-harness-protocols.md.
    mid_turn_injection: Literal[
        "queue",            # write user frame, harness queues for next boundary (Claude)
        "interrupt_restart",# call interrupt, then start a new turn with the new prompt (Codex)
        "http_post",        # POST to live session message endpoint (OpenCode)
        "none",             # adapter does not implement injection in this build
    ] = "none"
    supports_interrupt: bool = False     # honors `InterruptFrame` regardless of injection mode
    supports_cancel: bool = True          # all adapters must honor `CancelFrame`
    supports_runtime_model_switch: bool = False
    supports_cost_tracking: bool = True
    supports_structured_reasoning_stream: bool = False
```

`mid_turn_injection` is a **semantic enum** because the wire-level
behavior is honestly different across the three harnesses, and the UI
needs to render the difference. Per the
[findings doc](../findings-harness-protocols.md): a Claude user sees
"message queued for next turn"; a Codex user sees "this will interrupt
the current turn"; an OpenCode user sees a normal send button. **Don't
lie about wire-level behavior to fake uniformity.**

`supports_cost_tracking` and `supports_structured_reasoning_stream` are
honesty flags called out by the findings doc — Codex's companion-style
adapter doesn't surface per-token usage or `item/reasoning/delta`
streaming today, so the adapter declares that and the consumer renders
accordingly.

`supports_cancel` defaults `True` because every adapter must honor a
`CancelFrame` — that is the lifecycle hook for the streaming spawn
process itself, not a harness-specific capability. The interface
contract is "you accept the frame and tear down your subprocess
cleanly."

### Capability advertisement on the wire

Capability is broadcast to consumers via a `CAPABILITY` AG-UI event
emitted on spawn start, **before** any other event. The event payload
is the `HarnessCapabilities` model serialized to the AG-UI envelope.
This is a meridian-channel extension to the AG-UI taxonomy, not a
field redefinition — the rest of the events are unchanged.

The `CAPABILITY` event is the on-wire half of the same information
returned by `adapter.capabilities`. Two surfaces, same data: callers
that hold an adapter handle in-process read `capabilities` directly;
callers downstream of a streaming spawn (the Go backend, the
frontend, a sibling CLI) read it from the `CAPABILITY` event on the
event stream.

## What Does Not Change

- **`InProcessHarness` and `direct.py`** stay exactly as they are.
  The in-process Anthropic Messages API adapter does not participate
  in subprocess streaming; its `supports_stream_events=False` flag is
  a useful sentinel and stays. If we ever want streaming AG-UI from
  `direct.py`, that is a separate work item with very different
  trade-offs (no subprocess, no wire format to translate, native
  Python event objects). Reviewers should not flag direct.py as a
  gap — it is an explicit non-goal here.
- **`StreamEvent`** stays as the internal parsed-line type used by
  `launch/stream_capture.py`. The pre-existing parsing pipeline is
  load-bearing for `output.jsonl`, `report.md` extraction, and the
  fallback chain in `launch/extract.py` and `launch/report.py`. AG-UI
  events are a **second** event family the same line stream
  produces, not a replacement for `StreamEvent`.
- **`SpawnResult`** stays as the post-hoc summary returned at the end
  of a non-streaming spawn. Streaming spawns still emit a
  `RUN_FINISHED` event and write the same `report.md`/`output.jsonl`
  artifacts; `SpawnResult` is the in-process tail of that for
  callers that ran a non-streaming `meridian spawn create`.
- **`SpawnParams`** stays. Streaming-mode invocation lives in
  `launch_types.py` (a streaming launch flavor) so the prepared-plan
  and dry-run paths in `ops/spawn/prepare.py` and `ops/spawn/models.py`
  do not have to learn a new prompt-assembly shape.
- **`registry.py`** stays unless typing forces a small registration
  update for the new capability.

## Extension Points That Are Out Of Scope

- **A second `HarnessAdapter` family** for interactive vs batch tools.
  Not needed; the streaming-mode launch flavor handles the difference.
- **Approval gating** as a new method. Approvals stay in the existing
  permissions resolver path. The findings doc notes Codex's
  `item/*/requestApproval` requests; for V0 the Codex adapter
  auto-accepts (matching companion's posture) and surfaces approval
  events on the AG-UI stream as `TOOL_CALL_START` with metadata. Real
  approval gating is a follow-up.
- **Runtime model switching as an `inject_model` control frame.** Not
  in V0 — none of the three harnesses support it natively (per
  findings), and faking it would mean restarting the harness, which
  is what `cancel` + new spawn already does.

## Source File Map

| File | Status | Why |
|---|---|---|
| `harness/adapter.py` | extends | New methods on `SubprocessHarness`, new fields on `HarnessCapabilities`, new defaults on `BaseSubprocessHarness` |
| `harness/ag_ui_events.py` | **new** | AG-UI event model + emitter interface + per-tool config model |
| `harness/control_channel.py` | **new** | Control frame model + reader + dispatcher interface |
| `harness/launch_types.py` | extends | Streaming-mode launch flavor metadata |
| `harness/common.py` | extends carefully | Shared parse helpers grow; **do not** become the dumping ground for adapter-specific translation |
| `harness/transcript.py` | unchanged | Stays text-only; AG-UI is wire-format, not transcript |
| `harness/direct.py` | **unchanged** | In-process; out of scope |
| `harness/registry.py` | unchanged or trivial | Typing update only if needed |

For consumers (`launch/`, `lib/state/`, `lib/ops/spawn/`, `cli/`), see
[`../refactor-touchpoints.md`](../refactor-touchpoints.md). The
abstraction grows where the abstraction lives; the consumers grow
where the streaming-mode launch and `meridian spawn inject` plumbing
needs them.
