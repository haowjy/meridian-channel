# Architecture Simplification

Date added: 2026-03-08
Status: `proposed`
Priority: `high`

## Problem

The codebase has ~100 files, ~18,800 lines, and an 11-layer architecture for what is fundamentally a CLI that launches AI agent subprocesses and tracks them via JSONL files. The architecture has outgrown the problem:

- **11 layers with violated ordering**: `harness/direct.py` (Layer 5) imports from `ops/registry.py` (Layer 9). The "strict layered architecture" documented in ARCHITECTURE.md is aspirational, not actual.
- **OperationSpec registry**: 7-field ceremony per operation to mediate between CLI and MCP, but the CLI doesn't use the registry — it calls sync handlers directly. The MCP server is the only real consumer and it's 83 lines.
- **Spawn split across 6 files**: The single most important feature requires reading `spawn.py` (748), `_spawn_execute.py` (893), `_spawn_prepare.py` (373), `_spawn_models.py` (322), `_spawn_query.py` (295), `_utils.py` (18) — 2,649 lines across 6 files.
- **~20 files under 90 lines** that exist solely to hold 1-2 functions or types, adding import chains and navigation overhead without justifying separation.
- **Unnecessary `TYPE_CHECKING` guards** were hiding dependency violations and caused a Pydantic runtime bug (already fixed).

## Target Architecture

### 4 layers + surface (down from 11)

```
Layer 0: Foundation    types, domain, context, config, safety
Layer 1: Harness       adapter protocol + per-harness implementations
Layer 2: Engine        state stores, subprocess exec, prompt/extract
Layer 3: Operations    spawn/space/config/models business logic
Surface: CLI + MCP     thin dispatch, no business logic
```

### Target directory structure (~60 files, down from ~100)

```
src/meridian/
  cli/
    main.py               # Entry point + root command
    spawn.py              # Spawn subcommands
    space.py              # Space subcommands
    output.py             # Output sink impls (absorb format_helpers.py)
    catalog_cmd.py        # Models + skills + report combined
    config_cmd.py         # Config subcommands
  server/
    main.py               # MCP server — explicit tool registration, no registry
  lib/
    types.py              # NewType identifiers
    domain.py             # Trimmed: remove unused models
    context.py            # RuntimeContext
    sink.py               # OutputSink protocol
    logging.py            # Logging config
    util.py               # serialization + formatting merged
    config/
      settings.py         # MeridianConfig (absorb _paths.py)
      agent.py            # Agent profile parsing
      models.py           # aliases + routing + catalog + discovery merged
      skills.py           # skill.py + skill_registry.py merged
    safety/
      permissions.py      # Keep
      budget.py           # Keep
      guardrails.py       # Keep
      redaction.py        # Keep
    harness/
      adapter.py          # Protocol + registry + launch_types merged
      claude.py           # Keep
      codex.py            # Keep
      opencode.py         # Keep
      direct.py           # Keep, fix layering via lazy imports
      common.py           # _common + _strategies merged
      materialize.py      # Absorb layout.py
      session_detection.py
    state/
      paths.py            # Keep
      spawn_store.py      # Absorb id_gen.py
      artifact_store.py   # Keep
    exec/
      spawn.py            # Absorb env.py, errors.py, timeout.py, terminal.py
      signals.py          # Absorb process_groups.py
    prompt/
      compose.py          # assembly + sanitize + compose merged
      reference.py        # Keep
    extract/
      finalize.py         # Absorb _io.py
      report.py           # Keep
      files_touched.py    # Keep
    space/
      space_file.py       # Absorb crud.py
      session_store.py    # Keep
      launch_command.py   # Absorb _launch_types.py + _launch_resolve.py
      launch_process.py   # Keep
      summary.py          # Keep
    ops/
      spawn.py            # Merge all 6 spawn files (or spawn.py + spawn_exec.py)
      space.py            # Keep
      config.py           # Keep
      models.py           # Absorb skills.py
      report.py           # Keep
      diag.py             # Keep
      runtime.py          # Promote from _runtime.py
```

### Key eliminations

**OperationSpec registry** — the biggest structural win. Both cyclopts (CLI) and FastMCP (MCP server) already generate dispatch/schemas from Python function signatures + Pydantic types. The registry is a third abstraction doing what the other two already do. Replace with:
- CLI continues calling sync handlers directly (already the case)
- MCP server imports handlers directly and registers them with explicit `mcp.tool()` decorators (~20 more lines in server/main.py, eliminates ~400 lines of registry machinery)

**11-layer model** — replace with 4 layers. The current separation of "Prompt & Extract", "Space", "Execution" as distinct layers between Harness and Operations creates artificial boundaries. They are all part of the execution lifecycle.

**~20 small files** — absorb into their natural parents. Each adds an import chain and a file to navigate for minimal abstraction benefit.

## What Stays As-Is

- **Harness adapter protocol**: clean, well-justified, genuinely abstracts harness differences
- **State stores** (spawn_store, session_store, space_file): JSONL/JSON file approach works
- **Config settings**: large (845 lines) but necessary — pydantic-settings with layered precedence
- **Safety module**: 4 files, 617 lines, well-scoped and right-sized
- **CLI framework** (cyclopts) and **MCP server** (FastMCP): both work, just need registry removal

## Phase Plan

### Phase 1: Merge small files (low risk, high impact)

Purely mechanical merges. No behavioral changes. ~20 files eliminated.

| Merge | Into | Lines absorbed |
|-------|------|----------------|
| `id_gen.py` | `spawn_store.py` | 70 |
| `formatting.py` + `serialization.py` | `util.py` | 55 |
| `process_groups.py` | `signals.py` | 29 |
| `errors.py` + `timeout.py` + `env.py` + `terminal.py` | `exec/spawn.py` | 472 |
| `layout.py` | `materialize.py` | 88 |
| `launch_types.py` | `adapter.py` | 28 |
| `_strategies.py` | `common.py` (rename from `_common.py`) | 120 |
| `_io.py` | `finalize.py` | 13 |
| `crud.py` | `space_file.py` | 70 |
| `sanitize.py` + `assembly.py` | `compose.py` | 168 |
| `catalog.py` + `routing.py` | `aliases.py` (or rename to `models.py`) | 68 |
| `skill.py` + `skill_registry.py` | `skills.py` | 294 |
| `_launch_types.py` + `_launch_resolve.py` + `launch.py` facade | `launch_command.py` | 297 |

Verification: `uv run pytest-llm` + `uv run pyright` after each merge.

Commit checkpoint: one commit per merge (or batch related merges).

### Phase 2: Consolidate spawn operations (medium risk, high impact)

Merge the 6 spawn files into 1-2 files. The code is already tightly coupled — the split creates indirection without isolation.

Option A (aggressive): Single `ops/spawn.py` (~2,600 lines). Large but coherent.

Option B (moderate): Two files:
- `ops/spawn.py` — handlers (create, list, show, wait, cancel, continue) + models + queries
- `ops/spawn_exec.py` — execution engine (blocking, background, streaming)

Also merge `_utils.py` (18 lines: `minutes_to_seconds` and `merge_warnings`) inline.

Verification: full test suite.

Commit checkpoint: "Consolidate spawn operations into spawn.py + spawn_exec.py"

### Phase 3: Remove OperationSpec registry (medium risk, medium impact)

1. Remove `ops/registry.py` (102 lines) and the lazy-loading `ops/__init__.py` (36 lines)
2. Remove all `operation(OperationSpec(...))` ceremony at bottom of each ops module (~150 lines total)
3. Rewrite `server/main.py` to import and register MCP tools explicitly
4. Update `harness/direct.py` to import handlers via lazy imports
5. Move `codec.py` (95 lines) contents into `server/main.py` (its only non-DirectAdapter consumer)

This eliminates ~400 lines of registry machinery and removes an entire abstraction layer.

Verification: full test suite + verify MCP server still registers all tools.

Commit checkpoint: "Remove OperationSpec registry; explicit MCP tool registration"

### Phase 4: Trim domain.py (low risk)

Audit and remove unused domain models. Candidates: `SpawnEdge`, `Span`, `WorkflowEvent`, `WorkflowEventId`, `SpanId`, `TraceId`. Verify each has zero runtime references before removing.

Verification: `uv run pytest-llm` + `uv run pyright` + grep for removed names.

Commit checkpoint: "Remove unused domain models"

### Phase 5: Update ARCHITECTURE.md (low risk)

Rewrite `docs/ARCHITECTURE.md` to reflect the simplified architecture:
- 4-layer diagram instead of 11
- Updated directory layout
- Remove OperationSpec registry documentation
- Simplify data flow diagrams

Commit checkpoint: "Update architecture documentation"

## Ordering Constraints

- Phase 1 is independent and can start immediately
- Phase 2 should follow Phase 1 (some files Phase 2 touches will have been modified by Phase 1 merges)
- Phase 3 can run after Phase 1, independent of Phase 2
- Phase 4 can run any time
- Phase 5 runs last

Phases 2 and 3 can be parallelized if done carefully (different file sets).

## Interaction with Other Plans

- **test-suite-and-strictness-cleanup.md**: The test rewrite should happen AFTER this refactor, or at least be aware of it. Merging files will move test targets. Coordinate so tests track the new file structure.
- **unified-launch-refactor.md** (done): That plan extracted `launch_resolve.py` and shared agent launch config. This refactor absorbs `launch_resolve.py` into the modules that use it (Phase 1).

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|------------|
| 1: Merge small files | Low | Mechanical, test coverage catches regressions |
| 2: Consolidate spawn ops | Medium | Large file, but code is already tightly coupled; tests exist |
| 3: Remove OperationSpec registry | Medium | Affects MCP server + DirectAdapter; need careful test updates |
| 4: Trim domain.py | Low | Grep-verified removal |
| 5: Update docs | Low | No code changes |

## Exit Criteria

- File count reduced from ~100 to ~60
- Layer count reduced from 11 to 4
- OperationSpec registry eliminated
- No `TYPE_CHECKING` usage in the codebase
- `uv run pytest-llm` passes
- `uv run pyright` passes with zero errors
- `docs/ARCHITECTURE.md` reflects the actual architecture
