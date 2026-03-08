# Architecture Simplification V2

Date added: 2026-03-08
Status: `proposed`
Priority: `high`

## Goal

Reorganize the codebase around the features Meridian actually has:

**2 big workflows:**
- **Spawn** — launch a child agent, track it, finalize results
- **Primary launch** — launch the primary agent in a space

**5 small features:**
- **Config** — TOML settings CRUD
- **Models catalog** — list/show/refresh model aliases + discovery
- **Skills catalog** — list/search/show skills
- **Report** — spawn-scoped markdown report CRUD
- **Doctor** — health check / state repair

**Shared infrastructure:**
- Harness adapters, file-backed stores, safety, prompt assembly, process execution

This plan keeps the real seams, removes the fake ones, and fixes three
organizational mistakes the current layout makes:

1. `config/` conflates app settings with feature catalogs (agents, skills, models)
2. `space/` conflates data stores with process execution
3. Primary launch and spawn execution duplicate the same harness lifecycle in
   different packages

## Design Principles

1. Organize by feature workflow, not by an aspirational layer diagram.
2. Group things that change together. Separate things that don't.
3. Keep shared infrastructure shared — don't bury common logic inside one surface.
4. Replace implicit global registration with an explicit manifest.
5. Reduce file count where it improves navigation, not as a goal by itself.
6. Avoid giant hotspot modules that make future edits and multi-agent work harder.
7. Preserve future extension seams without turning extension support into current scope.

## Target Architecture

### Target directory structure

```text
src/meridian/
  cli/                         # Cyclopts surface — thin dispatch, no business logic
    main.py                    # Entry point + root command
    spawn.py                   # Spawn subcommands
    space.py                   # Space subcommands
    output.py                  # Output sink impls
    config_cmd.py              # Config subcommands
    catalog_cmd.py             # Models + skills combined
    report_cmd.py              # Report subcommands (separate — own data model)
    doctor_cmd.py              # Doctor subcommand

  server/
    main.py                    # FastMCP surface — explicit tool registration

  lib/
    core/                      # Lightweight shared primitives
      types.py                 # NewType identifiers (SpaceId, SpawnId, etc.)
      domain.py                # Core frozen models (Spawn, TokenUsage, etc.)
      context.py               # RuntimeContext (MERIDIAN_* env vars)
      sink.py                  # OutputSink protocol
      logging.py               # Structured logging config
      codec.py                 # Input coercion (from ops/codec.py)
      util.py                  # Serialization + formatting merged

    config/                    # ONLY application settings
      settings.py              # MeridianConfig (pydantic-settings, absorb _paths.py)

    catalog/                   # "What's available?" — all discovery and parsing
      agent.py                 # Agent profile parsing (from config/agent.py)
      skill.py                 # Skill parsing + registry merged (from config/skill.py + skill_registry.py)
      models.py                # Aliases + discovery + routing + catalog merged (from config/aliases.py + discovery.py + routing.py + catalog.py)

    harness/                   # Adapter protocol + implementations
      adapter.py               # HarnessAdapter protocol + capabilities + types
      registry.py              # Adapter lookup and routing
      claude.py                # Claude CLI adapter
      codex.py                 # Codex CLI adapter
      opencode.py              # OpenCode CLI adapter
      direct.py                # Anthropic Messages API adapter
      common.py                # _common.py + _strategies.py merged
      materialize.py           # Skill/agent materialization (absorb layout.py)
      session_detection.py     # Harness-specific session ID extraction
      launch_types.py          # PromptPolicy, SessionSeed (stays here — see note below)

    state/                     # ALL file-backed stores together
      paths.py                 # Path resolution (SpacePaths, StatePaths)
      spawn_store.py           # Spawn event store (absorb id_gen.py)
      space_store.py           # Space metadata CRUD (from space/space_file.py)
      session_store.py         # Session persistence (from space/session_store.py — see note below)
      artifact_store.py        # Artifact storage and retrieval

    safety/                    # Unchanged — well-scoped, right-sized
      permissions.py
      guardrails.py
      budget.py
      redaction.py

    launch/                    # Unified "how to launch a harness process"
      resolve.py               # Model/agent/harness resolution (from launch_resolve.py + space/_launch_resolve.py)
      command.py               # Build harness CLI command (from space/_launch_command.py)
      process.py               # Fork/exec + stream + finalize (from space/_launch_process.py)
      types.py                 # Request/result types (from space/_launch_types.py)
      prompt.py                # Prompt assembly pipeline (from prompt/compose.py + assembly.py + sanitize.py)
      reference.py             # Reference file handling (from prompt/reference.py)
      extract.py               # Post-run extraction (from extract/finalize.py + _io.py)
      report.py                # Report extraction (from extract/report.py)
      files_touched.py         # File change detection (from extract/files_touched.py)
      signals.py               # Signal forwarding (from exec/signals.py + process_groups.py)
      env.py                   # Child process environment (from exec/env.py)
      errors.py                # Error classification + retry (from exec/errors.py)
      timeout.py               # Spawn timeout management (from exec/timeout.py)
      runner.py                # execute_with_finalization (from exec/spawn.py)
                               #   Hook point: event emission (events.jsonl writer + future event bus)
      terminal.py              # TTY detection (from exec/terminal.py)

    ops/                       # Business logic handlers
      manifest.py              # Explicit surface manifest (replaces registry.py)
      runtime.py               # Runtime context assembly (from _runtime.py)
      spawn/                   # Spawn feature package
        api.py                 # Public handlers: create/list/show/wait/cancel/continue/stats
        models.py              # Request/response models (from _spawn_models.py)
        prepare.py             # Payload validation + launch prep (from _spawn_prepare.py)
        execute.py             # Blocking/background execution (from _spawn_execute.py)
        query.py               # Show/list/reference resolution (from _spawn_query.py)
      space.py                 # Space lifecycle handlers
      config.py                # Config TOML handlers
      catalog.py               # Models + skills query handlers merged
      report.py                # Report CRUD handlers
      diag.py                  # Doctor handler

    space/                     # Thin: space lifecycle facade only
      launch.py                # Public entry point — delegates to launch/ internals
      summary.py               # Space summary generation
      crud.py                  # Higher-level space operations (or absorb into ops/space.py)
```

### What this achieves

- **`config/`** becomes what it says: application settings only (845 lines).
  Agent profiles, skills, and model catalogs move to `catalog/` where they
  belong (~1,100 lines of domain-specific loading code).

- **`state/`** becomes the single home for all file-backed stores. Space
  metadata and session tracking are state stores — they just happened to live
  under `space/` because they were about spaces. Moving them to `state/` makes
  the data layer coherent.

- **`launch/`** unifies the harness process lifecycle. Today, primary launch
  (`space/_launch_*.py`, ~900 lines) and spawn execution (`exec/spawn.py`,
  776 lines) do the same thing: resolve → build command → fork → stream →
  extract → finalize. Prompt assembly (`prompt/`, ~500 lines) and extraction
  (`extract/`, ~450 lines) are steps in this lifecycle, not standalone
  concerns. Putting them together means one place to understand "how does
  Meridian launch a harness."

- **`ops/`** becomes feature-oriented. Spawn gets a proper package. Models +
  skills handlers merge into `catalog.py`. No more `_spawn_*.py` underscore
  convention.

- **`space/`** shrinks to a thin facade. `launch.py` stays as a stable public
  entry point but delegates to `launch/` internals. State stores move out.

## Target Dependency Model

```text
Surfaces (cli/, server/, harness/direct.py)
    │
    ▼
Feature Handlers (ops/spawn/, ops/space.py, ops/config.py, ops/catalog.py, ...)
    │
    ▼
Launch Lifecycle (launch/)  ◄── Safety (safety/)
    │
    ▼
Shared Infrastructure (harness/, state/, catalog/, config/)
    │
    ▼
Core Primitives (core/)
```

Rules:
- Surfaces depend on ops and core, contain no business logic
- Feature handlers depend on launch, infrastructure, and core
- Launch depends on harness adapters, state stores, and core
- Infrastructure packages do not import surfaces or ops
- Core imports nothing from the rest of the codebase

## What Stays As-Is

- **Harness adapter protocol** and per-harness implementations — clean, well-justified
- **File-authoritative state stores** — JSONL/JSON approach works, just consolidating their home
- **Safety subsystem** — 4 files, ~620 lines, well-scoped
- **CLI framework** (cyclopts) and **MCP server** (FastMCP) — both work
- **`space/launch.py`** as a public entry point — callers already depend on it

## Plugin-Readiness Constraints

Plugin support is out of scope for this plan, but the refactor should avoid
making future extension materially harder.

Constraints:

- Keep adapter-facing contracts in neutral shared modules. Harness adapters
  should not need to import `launch/` internals just to implement prompt or
  session policy hooks.

- Keep `state/` focused on persistence and replay. Harness-specific cleanup or
  other side effects should live above the store layer.

- Keep `ops/manifest.py` explicit and data-driven so it can remain a clean
  composition point for built-in operations and possible future extension.

- Keep CLI/MCP feature groupings consistent with the actual feature boundaries
  in ops/state/domain so later extension points are obvious rather than
  scattered.

- Treat `launch/` as internal orchestration, not as a public extension API.
  Future extensibility, if added, should attach at `harness/`, `catalog/`, and
  `ops/manifest.py` instead.

## What Changes

### 1. Extract `catalog/` from `config/`

`config/` currently holds agent profile parsing (285 lines), skill
parsing + registry (294 lines), and model alias/discovery/routing/catalog
(792 lines). None of these are application configuration — they're domain
feature code that loads resources from disk.

Move to `lib/catalog/`:
- `config/agent.py` → `catalog/agent.py`
- `config/skill.py` + `config/skill_registry.py` → `catalog/skill.py`
- `config/aliases.py` + `config/discovery.py` + `config/routing.py` + `config/catalog.py` → `catalog/models.py`

`config/` retains only `settings.py` (absorbing `_paths.py`).

### 2. Consolidate state stores

`space/space_file.py` (137 lines) and `space/session_store.py` (435 lines)
are file-backed stores. They do JSONL append/replay, JSON CRUD, and fcntl
locking — exactly what `state/spawn_store.py` and `state/artifact_store.py`
do. They belong together.

Move to `lib/state/`:
- `space/space_file.py` → `state/space_store.py`
- `space/session_store.py` → `state/session_store.py`

Also absorb `state/id_gen.py` (70 lines) into `state/spawn_store.py`.

**Prerequisite for session_store move:** `cleanup_stale_sessions()` currently
calls `cleanup_materialized()` from `harness/materialize.py`, creating a
`state → harness` dependency that violates the target boundary. Before moving
to `state/`, extract the materialization cleanup into a callback parameter or
return the stale harness/chat pairs so the caller can handle cleanup. The
store's job is persistence — side-effecting into the harness layer is not its
concern.

### 3. Unify launch lifecycle

Today, launching a harness process is split across 4 packages:
- `space/_launch_*.py` — command building, process lifecycle, resolution (~900 lines)
- `exec/` — subprocess execution, signals, env, timeout, errors (~1,350 lines)
- `prompt/` — prompt assembly, references, sanitization (~500 lines)
- `extract/` — finalization, report extraction, files touched (~450 lines)

These are all steps in the same lifecycle: resolve → build prompt → build
command → fork process → stream output → extract results → finalize. Create
`lib/launch/` to hold the entire lifecycle.

This eliminates 3 tiny packages (`exec/`, `prompt/`, `extract/`) and unifies
the primary launch + spawn execution paths.

**`harness/launch_types.py` stays in `harness/`.** `PromptPolicy` and
`SessionSeed` are consumed by every harness adapter (`claude.py`, `codex.py`,
etc.) and by the launch command stack. Moving them into `launch/types.py`
would create `harness → launch` imports while `launch` already depends on
`harness`, reintroducing the exact import-cycle pressure the current placement
explicitly avoids. `space/_launch_types.py` (request/result types used only
by the launch stack) does move into `launch/types.py`.

### 4. Replace `OperationSpec` registry with explicit manifest

Replace `ops/registry.py` and import-time self-registration with
`ops/manifest.py`. The manifest defines, for each operation:
- canonical name
- CLI group/name
- MCP tool name
- description
- input/output models
- handler references
- surface flags (CLI-only, MCP-only)

All three surfaces (CLI, MCP, DirectAdapter) consume this one manifest.

### 5. Convert spawn to feature package

Move the 6 spawn files from underscore-prefixed flat modules into a proper
`ops/spawn/` package:
- `spawn.py` → `ops/spawn/api.py`
- `_spawn_models.py` → `ops/spawn/models.py`
- `_spawn_prepare.py` → `ops/spawn/prepare.py`
- `_spawn_execute.py` → `ops/spawn/execute.py`
- `_spawn_query.py` → `ops/spawn/query.py`
- `_utils.py` — inline where it belongs (18 lines)

### 6. Merge models + skills ops handlers

`ops/models.py` (382 lines) and `ops/skills.py` (124 lines) both answer
"what's available?" — they're the same feature ("catalog"). Merge into
`ops/catalog.py`.

### 7. Merge low-value tiny files

| Merge | Into | Lines absorbed |
|-------|------|----------------|
| `state/id_gen.py` | `state/spawn_store.py` | 70 |
| `extract/_io.py` | `launch/extract.py` | 13 |
| `exec/process_groups.py` | `launch/signals.py` | 29 |
| `formatting.py` + `serialization.py` | `core/util.py` | 55 |
| `harness/layout.py` | `harness/materialize.py` | 88 |
| `harness/_common.py` + `harness/_strategies.py` | `harness/common.py` | 593 |
| `prompt/sanitize.py` + `prompt/assembly.py` | `launch/prompt.py` | 168 |
| `space/_launch_types.py` | `launch/types.py` | 86 |

## Phase Plan

### Phase 1: Scaffold `core/` and merge tiny files

Create the `lib/core/` package and do the easy mechanical merges that don't
change any public APIs.

Work:
- Create `lib/core/` with `types.py`, `domain.py`, `context.py`, `sink.py`,
  `logging.py` — move from `lib/` root, leave re-exports at old paths
- Create `lib/core/util.py` merging `formatting.py` + `serialization.py`
- Move `ops/codec.py` → `core/codec.py`
- Merge `state/id_gen.py` into `state/spawn_store.py`
- Merge `harness/layout.py` into `harness/materialize.py`
- Merge `harness/_common.py` + `harness/_strategies.py` into `harness/common.py`
- Merge `extract/_io.py` into `extract/finalize.py`
- Merge `exec/process_groups.py` into `exec/signals.py`

Rules:
- Preserve old import paths via re-exports
- No behavior changes

Verification: `uv run pytest-llm` + `uv run pyright`

Commit checkpoint: "Scaffold core package and merge tiny files"

### Phase 2: Extract `catalog/` from `config/`

Create `lib/catalog/` and move the agent/skill/model loading code out of
`config/`.

Work:
- Create `lib/catalog/agent.py` (from `config/agent.py`)
- Create `lib/catalog/skill.py` (merge `config/skill.py` + `config/skill_registry.py`)
- Create `lib/catalog/models.py` (merge `config/aliases.py` + `config/discovery.py` + `config/routing.py` + `config/catalog.py`)
- Absorb `config/_paths.py` into `config/settings.py`
- Update all imports (ops/models.py, ops/skills.py, harness/materialize.py,
  prompt/compose.py, space/_launch_command.py, etc.)
- Leave re-exports at old paths temporarily

Verification: `uv run pytest-llm` + `uv run pyright`

Commit checkpoint: "Extract catalog package from config"

### Phase 3: Consolidate state stores

Move space-related stores into `lib/state/` alongside the other stores.

Work:
- Extract the `cleanup_materialized()` call out of `session_store.py`'s
  `cleanup_stale_sessions()`. Change the function to return stale
  `(harness_id, chat_id)` pairs instead of calling into the harness layer
  directly. The caller (`ops/diag.py`, `cli/main.py`) handles materialization
  cleanup with the returned pairs. This removes the `state → harness`
  dependency before the move.
- Move `space/space_file.py` → `state/space_store.py`
- Move `space/session_store.py` → `state/session_store.py`
- Update all imports (ops/space.py, ops/spawn.py, ops/diag.py,
  space/_launch_process.py, cli/main.py, etc.)
- Leave re-exports at old paths temporarily

Verification: `uv run pytest-llm` + `uv run pyright`

Commit checkpoints:
- "Extract materialization cleanup from session_store"
- "Consolidate state stores under lib/state"

### Phase 4: Unify launch lifecycle

Create `lib/launch/` and migrate the four execution-related packages into it.
This is the largest phase — break into sub-steps and commit after each.

Sub-step 4a: Create `launch/` scaffold with types and resolution
- Create `launch/types.py` (from `space/_launch_types.py` — request/result types only;
  `harness/launch_types.py` stays in `harness/` to avoid import cycles)
- Create `launch/resolve.py` (from `launch_resolve.py` + `space/_launch_resolve.py`)

Sub-step 4b: Move prompt assembly into `launch/`
- Create `launch/prompt.py` (merge `prompt/compose.py` + `prompt/assembly.py` + `prompt/sanitize.py`)
- Create `launch/reference.py` (from `prompt/reference.py`)

Sub-step 4c: Move extraction into `launch/`
- Create `launch/extract.py` (from `extract/finalize.py` + `extract/_io.py`)
- Create `launch/report.py` (from `extract/report.py`)
- Create `launch/files_touched.py` (from `extract/files_touched.py`)

Sub-step 4d: Move execution into `launch/`
- Create `launch/runner.py` (from `exec/spawn.py`)
- Create `launch/signals.py` (from `exec/signals.py` + `exec/process_groups.py`)
- Create `launch/env.py` (from `exec/env.py`)
- Create `launch/errors.py` (from `exec/errors.py`)
- Create `launch/timeout.py` (from `exec/timeout.py`)
- Create `launch/terminal.py` (from `exec/terminal.py`)

Sub-step 4e: Move primary launch command building
- Create `launch/command.py` (from `space/_launch_command.py`)
- Create `launch/process.py` (from `space/_launch_process.py`)
- Thin out `space/launch.py` to delegate to `launch/` internals

Sub-step 4f: Delete emptied packages
- Remove `exec/`, `prompt/`, `extract/` (after all re-exports are updated)
- Remove migrated `space/_launch_*.py` files

Rules:
- Commit after each sub-step
- Preserve `space/launch.py` as public facade
- Update all imports incrementally

Verification at each sub-step: `uv run pytest-llm` + `uv run pyright`

Commit checkpoints:
- "Move launch types and resolution into launch package"
- "Move prompt assembly into launch package"
- "Move extraction into launch package"
- "Move execution into launch package"
- "Move primary launch command building into launch package"
- "Remove emptied exec, prompt, extract packages"

### Phase 5: Replace registry with explicit manifest

Work:
1. Create `ops/manifest.py` with explicit operation metadata entries
2. Update CLI command modules to register from manifest
3. Update `server/main.py` to register MCP tools from manifest
4. Update `harness/direct.py` to build tool schemas from manifest
5. Remove `ops/registry.py` and lazy `ops/__init__.py` behavior
6. Move `ops/_runtime.py` → `ops/runtime.py`

Rules:
- Preserve parity across CLI, MCP, and DirectAdapter
- One metadata source of truth, zero import-time mutation

**Surface-agnostic design note:** The manifest data shape should be kept
surface-agnostic so a future HTTP/web surface (e.g., mobile observability
dashboard, remote steering API) can consume it the same way CLI and MCP do
today. No extra code now — just avoid baking CLI- or MCP-specific assumptions
into the manifest schema itself.

Verification: `uv run pytest-llm` + `uv run pyright` + manual sanity check
that CLI commands and MCP tool names match manifest entries

Commit checkpoint: "Replace operation registry with explicit surface manifest"

### Phase 6: Reshape ops into feature packages

Sub-step 6a: Convert spawn to feature package
- `spawn.py` → `ops/spawn/api.py`
- `_spawn_models.py` → `ops/spawn/models.py`
- `_spawn_prepare.py` → `ops/spawn/prepare.py`
- `_spawn_execute.py` → `ops/spawn/execute.py`
- `_spawn_query.py` → `ops/spawn/query.py`
- Inline `_utils.py` (18 lines) where it belongs

Sub-step 6b: Merge models + skills handlers
- Merge `ops/models.py` + `ops/skills.py` → `ops/catalog.py`

Sub-step 6c: Clean up remaining ops
- Thin `space/crud.py` — absorb into `ops/space.py` if redundant
- Remove `space/summary.py` if unused, or keep if ops/space.py needs it

Rules:
- Preserve public handler names
- Keep `ops/spawn/api.py` focused on entrypoints
- Don't create single-file sub-packages for small ops (space, config, report, diag stay as flat files)

Verification: `uv run pytest-llm` + `uv run pyright`

Commit checkpoints:
- "Convert spawn operations to feature package"
- "Merge models and skills ops into catalog"

### Phase 7: Clean up re-exports, trim dead types, update docs

Work:
- Remove all temporary re-export shims from old paths
- Audit and remove unused domain types (candidates: `SpawnEdge`, `Span`,
  `WorkflowEvent`, `WorkflowEventId`, `SpanId`, `TraceId`)
- Update `docs/ARCHITECTURE.md` to describe the real structure
- Remove references to the old 11-layer model and operation registry

Verification: `uv run pytest-llm` + `uv run pyright` + grep for removed
symbols

Commit checkpoint: "Remove compatibility shims, trim dead types, update docs"

## Ordering Constraints

- Phase 1 must land before any broad import migration (establishes core/).
- Phases 2 and 3 are independent of each other and can run in parallel.
- Phase 4 should follow phases 2–3 so the state stores and catalog are
  already settled before moving execution code.
- Phase 5 can run after phase 1 but ideally after phase 4 so the launch
  package is stable.
- Phase 6 should follow phase 5 so spawn migration doesn't overlap with
  registry migration.
- Phase 7 runs last.

```text
Phase 1 ──┬── Phase 2 ──┐
           │             ├── Phase 4 ── Phase 5 ── Phase 6 ── Phase 7
           └── Phase 3 ──┘
```

## Interaction With Other Plans

- **`plans/test-suite-and-strictness-cleanup.md`**
  - should track the new package boundaries after they settle
  - avoid rewriting tests around old paths right before these moves
  - best to run after Phase 6 when the module layout is stable

- **`plans/unified-launch-refactor.md`** (done)
  - the launch facade introduced there is preserved (`space/launch.py`)
  - the `launch_resolve.py` it created moves into `launch/resolve.py`

## Risks

| Phase | Risk | Why |
|-------|------|-----|
| 1: Scaffold + merge tiny | Low | Additive, mechanical merges |
| 2: Extract catalog | Low | Mostly move + rename + update imports |
| 3: Consolidate state | Low | Same — move + rename |
| 4: Unify launch | Medium-High | Largest phase, touches execution paths |
| 5: Replace registry | Medium | Affects all command/tool surfaces |
| 6: Reshape ops | Medium | Spawn is the densest workflow |
| 7: Clean up + docs | Low | Dead code removal + docs |

Phase 4 is the riskiest because it merges 4 packages into 1. The sub-step
breakdown mitigates this — each sub-step is independently committable and
testable. If any sub-step proves too disruptive, the launch package can
absorb only part of the lifecycle and leave the rest where it is.

## Exit Criteria

- `config/` contains only application settings
- `catalog/` owns all agent/skill/model discovery and parsing
- `state/` owns all file-backed stores (spawn, space, session, artifact)
- `launch/` owns the entire harness launch lifecycle
- The operation registry is gone, replaced by an explicit manifest
- Spawn code lives in `ops/spawn/` package, not six underscore files
- `space/launch.py` remains a stable public facade
- No temporary re-export shims remain
- `docs/ARCHITECTURE.md` matches the actual codebase
- `uv run pytest-llm` passes
- `uv run pyright` passes with zero errors

## Non-Goals

- Hitting an arbitrary file-count target
- Designing or implementing a Python plugin system in this plan
- Collapsing every small file regardless of responsibility
- Replacing the harness adapter protocol or registry
- Changing data storage away from file-backed state
- Broad product-behavior changes unrelated to architecture
- Rewriting tests (separate plan)
