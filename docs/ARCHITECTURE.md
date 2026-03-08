# Architecture

Meridian is a coordination layer for multi-agent systems. It is not a filesystem, execution engine, or data warehouse. It provides scaffolding for launching, tracking, and inspecting AI agent spawns across multiple harnesses.

## System Overview

```mermaid
graph TD
    User["User / Parent Agent"] --> CLI["CLI<br/>cli/main.py"]
    User --> MCP["MCP Server<br/>server/main.py"]

    CLI --> Ops["Operations Layer<br/>ops/"]
    MCP --> Ops

    Ops --> Safety["Safety<br/>safety/"]
    Ops --> Config["Config<br/>config/"]
    Ops --> Harness["Harness Layer<br/>harness/"]
    Ops --> Space["Space Management<br/>space/"]
    Ops --> State["State Layer<br/>state/"]

    Harness --> Claude["Claude Adapter"]
    Harness --> Codex["Codex Adapter"]
    Harness --> OpenCode["OpenCode Adapter"]

    Space --> State
    Space --> Harness

    State --> FS[".meridian/.spaces/"]
```

## Layer Dependency Order

The codebase follows strict layered architecture. Each layer may only import from layers below it.

```mermaid
graph BT
    L0["Layer 0: Foundation<br/>types.py, sink.py, formatting.py"]
    L1["Layer 1: Domain<br/>domain.py, context.py"]
    L2["Layer 2: State<br/>paths.py, spawn_store.py, artifact_store.py"]
    L3["Layer 3: Config<br/>settings.py, agent.py, aliases.py, discovery.py"]
    L4["Layer 4: Safety<br/>permissions.py, budget.py, guardrails.py"]
    L5["Layer 5: Harness<br/>adapter.py, claude.py, codex.py, opencode.py"]
    L6["Layer 6: Prompt & Extract<br/>assembly.py, finalize.py, report.py"]
    L7["Layer 7: Space<br/>launch.py, session_store.py, space_file.py"]
    L8["Layer 8: Execution<br/>exec/spawn.py, signals.py"]
    L9["Layer 9: Operations<br/>ops/spawn.py, ops/space.py, ops/config.py"]
    L10["Layer 10: Surfaces<br/>cli/main.py, server/main.py"]

    L0 --> L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L7 --> L8 --> L9 --> L10
```

---

## Core Concepts

### Space

A self-contained agent ecosystem. Each space has a primary agent and zero or more child spawns, all sharing a filesystem under `.meridian/.spaces/<space-id>/fs/`. Two states: `active` and `closed`.

### Spawn

A single agent execution within a space. Spawns are launched via `meridian spawn`, tracked via JSONL events, and can be nested (a spawn can create child spawns).

### Harness

An AI backend adapter. The same `meridian spawn` command works across Claude, Codex, and OpenCode. Each harness translates spawn parameters into the native CLI invocation for that backend.

### Agent Profile

A YAML-frontmatter markdown file defining an agent's capabilities: model, skills, sandbox permissions, and system prompt body.

### Skill

Domain knowledge loaded into an agent at launch time. Skills survive context compaction because they are injected fresh on every launch/resume.

---

## Directory Layout

```
src/meridian/
  cli/                    # Command-line interface (cyclopts)
    main.py               # Entry point, global options, command dispatch
    spawn.py              # Spawn subcommand handlers
    output.py             # Output sink (text/json/agent mode)
  server/                 # MCP server (FastMCP on stdio)
    main.py               # Auto-registers all ops as MCP tools
  lib/
    types.py              # NewType identifiers (SpaceId, SpawnId, ModelId, ...)
    domain.py             # Frozen Pydantic domain models
    context.py            # RuntimeContext from environment variables
    sink.py               # Output sink protocol
    formatting.py         # Display formatting
    serialization.py      # JSON serialization helpers
    config/               # Configuration loading
      settings.py         # pydantic-settings BaseSettings (TOML + env)
      agent.py            # Agent profile parsing (YAML frontmatter)
      skill.py            # Skill spec loading
      aliases.py          # Model alias resolution
      discovery.py        # Agent/skill filesystem discovery
      routing.py          # Model-to-harness routing rules
    safety/               # Permission and budget enforcement
      permissions.py      # PermissionTier enum, flag resolution
      budget.py           # Token budget tracking
      guardrails.py       # Content guardrails
      redaction.py        # Secret redaction
    harness/              # AI backend adapters
      adapter.py          # HarnessAdapter protocol, SpawnParams, SpawnResult
      registry.py         # HarnessRegistry (model routing)
      claude.py           # Claude Code adapter
      codex.py            # Codex CLI adapter
      opencode.py         # OpenCode adapter
      direct.py           # Direct (in-process) adapter
      layout.py           # Harness directory layout
      materialize.py      # Copy agents/skills into harness dirs
      launch_types.py     # Launch parameter types
      session_detection.py# External session log parsing
    space/                # Space lifecycle management
      launch.py           # Primary agent launch orchestration
      space_file.py       # space.json CRUD
      session_store.py    # Session tracking (JSONL)
      crud.py             # Space create/list/close
    state/                # File-backed state persistence
      paths.py            # SpacePaths, StatePaths resolution
      spawn_store.py      # Spawn event store (JSONL)
      artifact_store.py   # Artifact storage
      id_gen.py           # Sequential ID generation
    exec/                 # Subprocess execution
      spawn.py            # Async subprocess orchestration
      signals.py          # Signal forwarding (SIGINT/SIGTERM)
      process_groups.py   # Process group management
    ops/                  # Business logic operations
      registry.py         # OperationSpec + global registry
      spawn.py            # spawn.create, spawn.list, spawn.show, spawn.wait
      space.py            # space.start, space.resume, space.list
      config.py           # config.get, config.set, config.init
      report.py           # report.show, report.create
      models.py           # models.list, models.show
      skills.py           # skills.list
      diag.py             # doctor diagnostics
      codec.py            # Input coercion and schema generation
    prompt/               # Prompt composition
      assembly.py         # Assemble prompt from parts
      reference.py        # Reference file handling
    extract/              # Post-spawn extraction
      finalize.py         # Extract report, tokens, files from output
      report.py           # Report extraction logic
      files_touched.py    # Detect modified files
```

---

## Data Flow: `meridian spawn`

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Ops as ops/spawn.py
    participant Safety as Safety Layer
    participant Harness as Harness Registry
    participant Store as State Store
    participant Exec as Execution Engine
    participant Child as Child Process

    CLI->>Ops: spawn_create_sync

    rect rgba(128, 128, 128, 0.08)
        Note over Ops,Safety: Preparation
        Ops->>Ops: resolve_runtime
        Ops->>Safety: build_permission_config
        Ops->>Harness: route_model
        Ops->>Ops: compose prompt + resolve agent
    end

    rect rgba(128, 128, 128, 0.08)
        Note over Store,Child: Execution
        Ops->>Store: start_spawn event
        Ops->>Harness: build_harness_command
        Ops->>Exec: execute_with_finalization
        Exec->>Child: asyncio subprocess
        Child-->>Exec: stdout/stderr stream
        Exec->>Exec: parse stream events
    end

    rect rgba(128, 128, 128, 0.08)
        Note over Ops,Store: Finalization
        Exec->>Exec: extract report + tokens + files
        Ops->>Store: finalize_spawn event
    end

    Ops-->>CLI: SpawnActionOutput
```

## Data Flow: `meridian start`

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Space as Space Manager
    participant Config as Config
    participant Harness as Harness Layer
    participant Process as Harness Process

    CLI->>Space: SpaceLaunchRequest

    rect rgba(128, 128, 128, 0.08)
        Note over Space,Harness: Context Resolution
        Space->>Config: load_config
        Space->>Harness: resolve_harness
        Space->>Harness: materialize agents/skills
        Space->>Harness: build_harness_command
    end

    Space->>Process: run_harness_process
    Process-->>CLI: interactive I/O
    Process-->>Space: SpaceLaunchResult
```

---

## State Model

All state lives in files. No database. JSONL append-only events for spawns and sessions, JSON for space metadata. Atomic writes via `tmp` + `os.replace()`, concurrency via `fcntl.flock`.

```mermaid
graph TD
    Root[".meridian/"] --> Spaces[".spaces/"]
    Spaces --> SpaceDir["&lt;space-id&gt;/"]
    SpaceDir --> SJ["space.json"]
    SpaceDir --> SpJ["spawns.jsonl"]
    SpaceDir --> SeJ["sessions.jsonl"]
    SpaceDir --> FS["fs/<br/>(shared filesystem)"]
    SpaceDir --> SpDir["spawns/"]
    SpDir --> Sp1["&lt;spawn-id&gt;/"]
    Sp1 --> Out["output.jsonl"]
    Sp1 --> Err["stderr.log"]
    Sp1 --> Tok["tokens.json"]
    Sp1 --> Rep["report.md"]
```

### Event Sourcing

Spawn lifecycle is tracked as append-only JSONL events in `spawns.jsonl`:

```json
{"event": "start", "spawn_id": "p1", "model": "claude-sonnet-4-6", "prompt": "...", "ts": "..."}
{"event": "finalize", "spawn_id": "p1", "status": "succeeded", "duration_secs": 42.5, "ts": "..."}
```

Session lifecycle follows the same pattern in `sessions.jsonl`. Both use Pydantic event models (`SpawnStartEvent`, `SessionStartEvent`, etc.) for typed serialization at I/O boundaries.

---

## Harness System

The harness layer abstracts AI backend differences behind a common protocol.

```mermaid
graph TD
    Registry["HarnessRegistry<br/>route_model"] --> CA["ClaudeAdapter"]
    Registry --> CX["CodexAdapter"]
    Registry --> OC["OpenCodeAdapter"]
    Registry --> DA["DirectAdapter"]

    CA --> Proto["HarnessAdapter Protocol"]
    CX --> Proto
    OC --> Proto
    DA --> Proto

    Proto --- BC["build_command<br/>SpawnParams -> CLI args"]
    Proto --- PS["parse_stream_event<br/>stdout line -> StreamEvent"]
    Proto --- EU["extract_usage<br/>artifacts -> TokenUsage"]
```

Each adapter translates `SpawnParams` into native CLI args:
- **Claude**: `claude eval --json --model X --prompt Y`
- **Codex**: `codex exec --model X --prompt Y`
- **OpenCode**: `opencode --provider google --model X`

The registry routes models to the correct adapter based on model family (`claude-*` to Claude, `gpt-*` to Codex, `gemini-*` to OpenCode).

---

## Operation Registry

All business logic is registered as `OperationSpec` entries in a single global registry. Both CLI and MCP server consume the same specs.

```mermaid
graph LR
    subgraph Registration
        SpawnOps["ops/spawn.py"]
        SpaceOps["ops/space.py"]
        ConfigOps["ops/config.py"]
        ModelOps["ops/models.py"]
        ReportOps["ops/report.py"]
        SkillOps["ops/skills.py"]
    end

    SpawnOps --> R["OperationSpec Registry"]
    SpaceOps --> R
    ConfigOps --> R
    ModelOps --> R
    ReportOps --> R
    SkillOps --> R

    R --> CLI["CLI<br/>cyclopts dispatch"]
    R --> MCP["MCP Server<br/>FastMCP tools"]
```

Each `OperationSpec` declares:
- `handler` / `sync_handler` for async (MCP) and sync (CLI) execution
- `input_type` / `output_type` as Pydantic models for schema generation
- `cli_group` / `cli_name` for CLI routing
- `mcp_name` for MCP tool registration

```python
operation(OperationSpec(
    name="spawn.create",
    handler=spawn_create,
    sync_handler=spawn_create_sync,
    input_type=SpawnCreateInput,
    output_type=SpawnActionOutput,
    cli_group="spawn",
    cli_name=None,
    mcp_name="spawn_create",
))
```

---

## Configuration

Configuration uses pydantic-settings `BaseSettings` with layered precedence:

```mermaid
graph LR
    D["Defaults"] --> PT["Project TOML<br/>meridian.toml"]
    PT --> UT["User TOML<br/>~/.config/meridian/config.toml"]
    UT --> ENV["Environment Variables<br/>MERIDIAN_*"]
    ENV --> CLIFlags["CLI Flags"]
```

Higher layers override lower layers. Key env vars:

| Variable | Maps to |
|----------|---------|
| `MERIDIAN_MODEL` | `primary.model` |
| `MERIDIAN_HARNESS` | `primary.harness` |
| `MERIDIAN_MAX_TURNS` | `primary.max_turns` |
| `MERIDIAN_BUDGET` | `primary.budget` |
| `MERIDIAN_FORMAT` | `output.format` |

---

## Safety

### Permission Tiers

```
read-only         No file modifications allowed
workspace-write   Can modify files within the repo
full-access       Unrestricted access
```

Permissions flow: CLI/profile/config -> `PermissionConfig` -> `PermissionResolver` -> harness-specific flags (e.g., Claude's `--allowedTools`).

### Budget Tracking

Token budgets are enforced per-spawn. `LiveBudgetTracker` monitors cumulative usage and raises `BudgetBreach` when limits are exceeded.

---

## Execution Engine

The execution engine (`exec/spawn.py`) manages child processes:

```mermaid
graph TD
    Start["start_spawn"] --> Build["build_harness_command"]
    Build --> Subprocess["asyncio.create_subprocess_exec"]
    Subprocess --> Stream["Async readline loop<br/>parse StreamEvents"]
    Subprocess --> Signals["SignalForwarder<br/>SIGINT/SIGTERM passthrough"]
    Subprocess --> Timeout["Timeout watchdog<br/>SIGTERM -> grace -> SIGKILL"]
    Stream --> Finalize["extract report + tokens + files"]
    Finalize --> Store["finalize_spawn event"]
```

1. **Launch**: `asyncio.create_subprocess_exec` with inherited env + meridian context vars
2. **Streaming**: Async readline loop parsing stdout into `StreamEvent` objects
3. **Signals**: `SignalForwarder` captures SIGINT/SIGTERM from the parent and forwards to the child process group
4. **Timeout**: Watchdog sends SIGTERM after timeout, then SIGKILL after a grace period
5. **Depth limiting**: `MERIDIAN_DEPTH` env var prevents runaway recursive nesting

---

## Spawn Nesting

Spawns can create child spawns. Each child inherits `MERIDIAN_SPACE_ID` and receives incremented depth tracking.

```mermaid
graph TD
    Primary["Primary Agent<br/>depth=0"] --> S1["Spawn p1<br/>depth=1"]
    Primary --> S2["Spawn p2<br/>depth=1"]
    S1 --> S3["Spawn p3<br/>depth=2"]
    S1 --> S4["Spawn p4<br/>depth=2"]
```

Context propagation per child: `MERIDIAN_SPAWN_ID`, `MERIDIAN_PARENT_SPAWN_ID`, `MERIDIAN_DEPTH` (parent + 1). The shared filesystem at `fs/` enables data passing between siblings and across depths.

---

## Type System

All identifiers use `NewType` wrappers for compile-time safety:

```python
SpaceId   = NewType("SpaceId", str)
SpawnId   = NewType("SpawnId", str)
ModelId   = NewType("ModelId", str)
HarnessId = NewType("HarnessId", str)
```

All domain models and I/O types are frozen Pydantic `BaseModel` instances. State persistence uses `model_validate()` / `model_dump()` at I/O boundaries. No raw dataclasses remain in the codebase.
