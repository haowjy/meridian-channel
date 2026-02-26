# Run Output Streaming

**Status:** done (all slices 1-5 implemented)

## Problem

`meridian run` dumps the full harness output (60KB+ of raw stream-json) to stdout. This is unusable for both humans and orchestrators. Meanwhile, the shell-based `run-agent.sh` already solves this by routing stdout to a file and only showing stderr + the final report.

The Python CLI has `parse_stream_event()` defined on every harness adapter but **never calls it** during execution. The structured event infrastructure exists but is unwired.

## Design

### Output routing

| Stream | Destination | Always? |
|--------|------------|---------|
| Full raw harness output | `output.jsonl` artifact (disk) | Yes |
| Stderr passthrough | Terminal stderr | Yes |
| Filtered/formatted events | Terminal stderr | Configurable |
| Report | `report.md` artifact + displayed at end | Yes |
| Final summary line | Terminal stderr | Yes |

**Stdout is reserved for structured/machine-readable output only** (e.g., `--format json`). All human-readable progress, filtered events, and summary lines go to stderr. This matches the CLI contract (`cli-contract.md`: stdout = data, stderr = progress/diagnostics) and allows piping `meridian run` output cleanly.

Default terminal stdout shows only:
```
r33  gpt-5.3-codex  running...
r33  completed  45.2s  exit=0  tokens=12.4k
```

### Structured event filtering

Wire `parse_stream_event()` into `_capture_stdout()` to classify each output line. Then apply a configurable filter to decide what reaches the terminal.

**Event categories:**

| Category | Examples | Default visibility |
|----------|---------|-------------------|
| `lifecycle` | run started, completed, failed | shown |
| `sub-run` | nested `meridian run` invocations | shown (compact) |
| `tool-use` | tool calls, file edits | hidden |
| `thinking` | model reasoning/thinking blocks | hidden |
| `assistant` | model text output | hidden |
| `error` | errors, warnings | shown |
| `progress` | status updates, checkpoints | hidden |
| `system` | retries, guardrail triggers, budget warnings, cancellations | shown |

### Configurable filters

In `.meridian/config.toml`:

```toml
[output]
# What event categories to show on terminal during runs
# Options: lifecycle, sub-run, tool-use, thinking, assistant, error, progress, system
show = ["lifecycle", "sub-run", "error", "system"]

# Or use a preset
# verbosity = "quiet"    # lifecycle + error only
# verbosity = "normal"   # lifecycle + sub-run + error (default)
# verbosity = "verbose"  # everything except thinking
# verbosity = "debug"    # everything, raw
```

CLI override: `--verbose` / `--quiet` / `--stream` (stream everything raw, like today).

Precedence: `--stream` flag > `--verbose`/`--quiet` flag > config.toml `output.show` > default preset.

### Sub-run visibility

When a run spawns a nested `meridian run` (tracked via `MERIDIAN_DEPTH`), the parent should see compact lifecycle events:

```
r33  gpt-5.3-codex  running...
r33  ├─ r34  claude-haiku-4-5 (reviewer)  started
r33  ├─ r34  completed  2.1s  tokens=3.2k
r33  completed  45.2s  exit=0  tokens=12.4k
```

This requires the child run to emit structured lifecycle events that the parent's stream parser can recognize and format. The `MERIDIAN_DEPTH` env var already tracks nesting depth.

### Event protocol

Each harness adapter's `parse_stream_event()` already returns `StreamEvent(event_type, raw_line, text)`. Extend `StreamEvent` to include a `category` field:

```python
@dataclass(frozen=True, slots=True)
class StreamEvent:
    event_type: str
    category: str          # NEW: lifecycle, sub-run, tool-use, thinking, etc.
    raw_line: str
    text: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)  # NEW: structured data
```

Each adapter maps its harness-specific event types to categories:
- Claude: `"result"` → lifecycle, `"tool_use"` → tool-use, `"assistant"` → assistant
- Codex: similar mapping from codex JSON events
- OpenCode: similar mapping

---

## Implementation Slices

### Slice 1: Route stdout to file, stop dumping to terminal

The minimum viable fix. Match `run-agent.sh` behavior.

**Files to modify:**
- `src/meridian/lib/exec/spawn.py` — `_capture_stdout()`: remove any terminal streaming, keep disk-only writes to `output.jsonl`. Already mostly correct (stdout doesn't go to terminal today — it's just returned as the raw output and the CLI dumps it).
- `src/meridian/cli/run.py` — the actual problem: the CLI `emit()` call sends the full `RunActionOutput` to stdout. The `RunActionOutput.format_text()` is compact, but the **harness raw output** may be leaking through the sync execution path.

**Actually investigate:** Trace exactly where the 60KB output appears. Is it from `emit(result)` or from stderr passthrough or from `sys.stdout` in spawn? Confirm before fixing.

**Tests:**
- Run a simple `meridian run -p "hi"` and verify only the summary line appears on stdout
- Full output still written to `output.jsonl` artifact

### Slice 2: Wire parse_stream_event into capture loop

Connect the existing but unused stream event parsing.

**Files to modify:**
- `src/meridian/lib/exec/spawn.py` — `_capture_stdout()`: after reading each line, call `harness.parse_stream_event(line)` to get a `StreamEvent`. Pass events to a new `event_observer` callback.
- `src/meridian/lib/exec/spawn.py` — `spawn_and_stream()`: accept a `harness: HarnessAdapter` parameter (or just the `parse_stream_event` callable) and an `event_observer` callback.
- `src/meridian/lib/harness/adapter.py` — extend `StreamEvent` with `category` and `metadata` fields.
- `src/meridian/lib/harness/claude.py`, `codex.py`, `opencode.py` — implement category mapping in `parse_stream_event()`.

**Tests:**
- Unit test: stream events are correctly categorized per harness
- Integration: event_observer receives categorized events during a run

### Slice 3: Terminal event formatter + filter

Display filtered events on the terminal during run execution.

**Files to create:**
- `src/meridian/lib/exec/terminal.py` — `TerminalEventFilter` that:
  - Accepts a set of visible categories
  - Formats events for terminal display (compact, single-line)
  - Handles sub-run indentation based on `MERIDIAN_DEPTH`
  - Writes to stderr (not stdout — stdout is for structured output)

**Files to modify:**
- `src/meridian/lib/ops/run.py` — `_execute_run_blocking()`: create a `TerminalEventFilter` and pass it as the `event_observer` to `spawn_and_stream()`
- `src/meridian/cli/run.py` — pass `--verbose` / `--quiet` / `--stream` flags through to control filter

**Default behavior:**
- Show: `lifecycle`, `sub-run`, `error`
- Hide: `tool-use`, `thinking`, `assistant`, `progress`

**Tests:**
- Filter correctly shows/hides events by category
- Sub-run events render with tree-style indentation
- `--verbose` shows all, `--quiet` shows only lifecycle+error, `--stream` shows raw

### Slice 4: Config-driven filter presets

Read event filter settings from `.meridian/config.toml` via `OperationRuntime.config`.

**Files to modify:**
- `src/meridian/lib/config/settings.py` — add `OutputConfig` to `MeridianConfig`:
  ```python
  @dataclass(frozen=True, slots=True)
  class OutputConfig:
      show: tuple[str, ...] = ("lifecycle", "sub-run", "error", "system")
      verbosity: str | None = None  # quiet/normal/verbose/debug preset
  ```
- `src/meridian/lib/exec/terminal.py` — `resolve_visible_categories()` gains an optional `config: OutputConfig | None` parameter. `TerminalEventFilter` receives resolved categories only (does not import or read config directly).
- `src/meridian/lib/ops/run.py` — read `OutputConfig` from `runtime.config`, pass to `resolve_visible_categories()`. CLI flags still override config.

**Depends on:** Config system plan Slice 2 (config wired into `OperationRuntime`). Not just Slice 1 — this slice must consume config through `runtime.config`, not by calling `load_config()` independently. This ensures consistent config threading across all operations.

**Note:** `OutputConfig` is the first extension point on `MeridianConfig` from outside the config plan. The config plan's loader (Slice 1) should be designed to parse arbitrary TOML sections into sub-dataclasses.

**Tests:**
- Config preset overrides default filter
- CLI flags override config
- Config consumed via `runtime.config`, not direct `load_config()` call

### Slice 5: Sub-run lifecycle event enrichment

Enrich the existing sub-run lifecycle events with protocol versioning and parent correlation for robust concurrent child-run tracing.

**Current state:** `_emit_subrun_event()` already emits basic `run.start` and `run.done` events (implemented in slices 1-3). This slice enriches the protocol.

**Files to modify:**
- `src/meridian/lib/ops/run.py` — enrich the existing `_emit_subrun_event()` output:
  ```json
  {"v": 1, "t": "meridian.run.start", "id": "r34", "parent": "r33", "model": "claude-haiku-4-5", "agent": "reviewer", "d": 1, "ts": 1740000000.123}
  {"v": 1, "t": "meridian.run.done", "id": "r34", "parent": "r33", "exit": 0, "secs": 2.1, "tok": 3200, "ts": 1740000002.234}
  ```
  New fields:
  - `v`: protocol version (start at 1, bump on breaking changes)
  - `parent`: parent run ID (from `MERIDIAN_PARENT_RUN_ID` env var) — enables tree reconstruction for concurrent children
  - `ts`: monotonic timestamp (`time.monotonic()` or epoch float) — establishes ordering for concurrent events
  - Event types namespaced as `meridian.run.*` to avoid collisions with harness-native `run.*` events
- `src/meridian/lib/harness/_common.py` — `parse_json_stream_event()`: recognize `meridian.*` event types (namespaced) and map to `sub-run` category
- `src/meridian/lib/ops/run.py` — set `MERIDIAN_PARENT_RUN_ID` in child env when spawning nested runs

**Post config-slice-3 verification:** After `base_skills.py` is deleted, verify that `_emit_subrun_event()` still emits the agent name correctly for default-profile runs (the `prepared.agent_name` path must still resolve).

**Tests:**
- Enriched events include `v`, `parent`, `ts` fields
- Parent run ID propagated via env var
- Namespaced event types parsed correctly
- Concurrent child runs produce distinguishable, ordered events
- Terminal formatter renders tree-style indentation using `parent` field

---

## Verification

Each slice:
1. All existing tests pass
2. `uv run ruff check src/ tests/`
3. `uv run pyright src/`
4. Manual smoke: `meridian run -p "hi"` shows compact output, not raw stream

## Dependencies

- Slices 1–3: done, independent of config system
- Slice 4: depends on config-system plan Slice 2 (config wired into `OperationRuntime`), not just Slice 1
- Slice 5: depends on Slice 2 (event parsing wired) — already done. Can execute in parallel with config S1–S2.
- Both plans heavily modify `run.py` (~1100 lines). Avoid concurrent slice execution that touches the same file.

## Resolved Questions

1. **stderr vs stdout:** Filtered terminal output goes to **stderr**. Stdout is reserved for structured/machine-readable output (`--format json`). This matches `cli-contract.md` (stdout = data, stderr = progress/diagnostics).

2. **`--stream` semantics:** `--stream` is **literal raw passthrough** — dumps the full harness output to stderr as-is (current behavior compatibility). `--verbose` is the formatted-but-all-categories mode. These are distinct: `--stream` bypasses event parsing entirely, `--verbose` still parses and formats.

3. **MCP subscription:** No SSE in this plan. If live event updates are needed for the MCP surface, add a pull-based `run_events(run_id, after_seq, limit)` MCP tool as a follow-up. The current `run_create` + `run_wait` / polling model is sufficient.
