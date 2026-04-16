# Workspace Config Refactor Agenda

This agenda covers structural rearrangements the planner must account for before or alongside feature work. Scope entries cite the live probe evidence so implementation phases can anchor their file lists to observed code, not memory.

**Dependency graph:** R01 → R02 (prep before rewire). R06 → R05 (domain core before workspace projection). R01/R02 and R06 have no file-level overlap and can be scheduled in any order or in parallel. R03 is follow-up only (conditional on post-R05 drift). R04 is folded into R01.

## R01 — Separate project-root file policy from `StatePaths`

Includes former R04 scope.

- **Type:** prep refactor
- **Why:** `StatePaths` is `.meridian`-scoped today. Adding `meridian.toml`, `workspace.local.toml`, or `MERIDIAN_WORKSPACE` logic there would mix project-root policy with local runtime state (`probe-evidence/probes.md:139-145`).
- **Scope:**
  - `src/meridian/lib/state/paths.py:21,33,127` — current `.meridian/config.toml` and `.meridian/.gitignore` policy live here (`probe-evidence/probes.md:68-72`).
  - `src/meridian/lib/config/settings.py:206-210` — project-config resolver currently depends on `StatePaths.config_path` (`probe-evidence/probes.md:72-74`).
  - `src/meridian/lib/config/settings.py:789-823` — project-root detection exists today as `resolve_repo_root`; R01 renames this to `resolve_project_root` and models root-level files as a cohesive layer (`probe-evidence/probes.md:143-145`).
  - Rename caller set from live probe (`rg -n "resolve_repo_root" src/ tests/`):
    `src/meridian/lib/catalog/models.py:30,40,299`,
    `src/meridian/lib/catalog/skill.py:8,97,143`,
    `src/meridian/lib/catalog/agent.py:10,168,209`,
    `src/meridian/lib/launch/plan.py:10,159`,
    `src/meridian/cli/main.py:1317,1320`,
    `src/meridian/lib/ops/runtime.py:12,63`,
    `src/meridian/lib/ops/catalog.py:21,189`,
    `src/meridian/lib/ops/config.py:16,346,348,776,826,845,871`,
    and `src/meridian/lib/config/settings.py:802`.
- **Exit criteria:**
  - A new project-root file abstraction (`ProjectPaths`) owns `meridian.toml`, `workspace.local.toml`, and `MERIDIAN_WORKSPACE`.
  - `StatePaths` no longer owns the canonical project-config path.
  - Project-root file policy can evolve without expanding the `.meridian` path object.
  - `resolve_repo_root` is renamed to `resolve_project_root` so the internal name matches the concept. No user-facing "repo root" term remains in spec leaves or CLI copy.
  - The `.meridian/.gitignore` `!config.toml` exception is removed as part of this refactor (see R04 below — folded here).

## R02 — Rewire the config command family end-to-end

- **Type:** prep refactor
- **Why:** Moving project config is not a resolver tweak. Loader, config commands, runtime bootstrap, CLI copy, and tests all currently point at `.meridian/config.toml` or `_config_path()` (`probe-evidence/probes.md:60-100`).
- **Scope:**
  - `src/meridian/lib/config/settings.py:206-227` — loader project/user config resolution (`probe-evidence/probes.md:72-74`).
  - `src/meridian/lib/ops/config.py:342-343,602-606,737-763,758,777,827,846,872` — config-path helper, bootstrap, and every config subcommand (`probe-evidence/probes.md:75-79`, `probe-evidence/probes.md:151-158`).
  - `src/meridian/lib/ops/runtime.py:66` — startup path that triggers bootstrap (`probe-evidence/probes.md:151-158`).
  - `src/meridian/lib/ops/manifest.py:242,266` and `src/meridian/cli/main.py:806-815` — user-facing command descriptions (`probe-evidence/probes.md:80-87`).
  - Live test/smoke hits from `rg -l "config\\.toml|_config_path" tests/`:
    `tests/smoke/config/init-show-set.md`,
    `tests/smoke/quick-sanity.md`.
- **Exit criteria:**
  - One `ProjectConfigState` (with states `absent | present`) is shared by the settings loader, config commands, bootstrap, and diagnostics.
  - All project-config reads and writes target `meridian.toml` through the shared `ProjectConfigState`; no command resolves project config from a different location.
  - Generic bootstrap (`ensure_state_bootstrap_sync`) no longer auto-creates project-root config; it creates only `.meridian/` runtime directories and `.meridian/.gitignore`.
  - CLI help, manifests, and tests all describe `meridian.toml` as the canonical project config.
  - `config migrate` does not exist; no legacy fallback code paths are introduced.

## R03 — Keep direct `--add-dir` emitters narrow after the interface extraction

- **Type:** follow-up only if post-R05 duplication remains
- **Why:** R05 subsumes the old "centralize ordered `--add-dir` planning" work by
  moving ordering/applicability into a harness-agnostic projection interface.
  A separate shared `--add-dir` emitter is only justified if the remaining
  Claude/Codex direct-flag materialization starts drifting after that.
- **Scope:**
  - `src/meridian/lib/harness/projections/project_claude.py` — final Claude CLI token emission.
  - `src/meridian/lib/harness/projections/project_codex_subprocess.py:189-227` — final Codex CLI token emission (`probe-evidence/probes.md:106-123`).
  - `src/meridian/lib/launch/text_utils.py:8-19` — first-seen dedupe semantics remain shared and load-bearing (`probe-evidence/probes.md:24-38`).
- **Exit criteria:**
  - If this follow-up is needed at all, it factors only direct `--add-dir`
    token emission.
  - Ordering, applicability, diagnostics, and OpenCode overlay handling remain
    owned by R05's projection interface, not by a new generic flag builder.

## R04 — Remove the `.meridian/.gitignore` `!config.toml` exception

- **Type:** folded into R01
- **Why:** The `.meridian/.gitignore` `!config.toml` exception is legacy scaffolding from when `.meridian/config.toml` was committed. With no migration and no legacy fallback, removing it is unconditional and belongs alongside R01.
- **Scope:**
  - `src/meridian/lib/state/paths.py:21,33` — `_GITIGNORE_CONTENT` and `_REQUIRED_GITIGNORE_LINES` currently preserve the exception (`probe-evidence/probes.md:70-71`).
- **Exit criteria:** folded into R01's exit criteria above. Normal runtime bootstrap does not preserve `.meridian/config.toml` as a committed exception.

## R05 — Extract a harness-agnostic workspace-projection interface

- **Type:** prep refactor
- **Why:** Day-1 support now spans three different mechanisms: Claude direct
  `--add-dir`, Codex direct `--add-dir` with a read-only ignored-state, and
  OpenCode config-overlay transport. Bolting OpenCode onto an `add_dirs`-centric
  core would leak harness detail across launch code and violate the project's
  "extend, don't modify" rule. R05 adds the `project_workspace()` adapter method
  per harness; the ordered-root computation lives in `launch/context_roots.py`
  as a domain-core pipeline stage inserted by R05 into the factory delivered
  by R06.
  **Depends on R06 invariants:** R06's domain core (one `build_launch_context()`
  factory, one `LaunchContext` sum type, 3 driving adapters routed through the
  factory with no composition of their own) gives R05 exactly one insertion
  point for the workspace pipeline stage. Without R06, R05 would need to wire
  workspace projection into every driving adapter independently.
- **Scope:**
  - `src/meridian/lib/harness/adapter.py:224-247` — extend the adapter contract
    with one workspace-projection seam.
  - `src/meridian/lib/launch/context.py:148-223` — insert workspace-projection
    as a pipeline stage inside the R06 domain-core factory
    `build_launch_context()`, after spec resolution and before env construction.
  - `src/meridian/lib/harness/claude_preflight.py:120-166` — stop treating
    workspace-root emission as inline Claude-only expansion; keep only
    projection-managed child/parent behavior here.
  - `src/meridian/lib/harness/projections/project_codex_subprocess.py:189-227`
    — append workspace projection after explicit passthrough and respect the
    read-only ignored-state.
  - `src/meridian/lib/harness/projections/project_codex_streaming.py` — keep
    the Codex streaming path on the same projection interface as the subprocess
    utility boundary.
  - `src/meridian/lib/harness/projections/project_opencode_subprocess.py:83-160`
    and `src/meridian/lib/harness/opencode.py:208-246` — add the
    `permission.external_directory` overlay path and its
    `OPENCODE_CONFIG_CONTENT` env materialization.
  - `src/meridian/lib/harness/projections/project_opencode_streaming.py` —
    keep OpenCode streaming projection on the same interface and env-additions
    channel as subprocess launch.
  - Surfacing touchpoints claimed by this refactor:
    `src/meridian/lib/ops/config.py`,
    `src/meridian/lib/ops/diag.py`,
    and new shared builder `src/meridian/lib/ops/config_surface.py`.
  - New modules:
    `src/meridian/lib/launch/context_roots.py` and
    `src/meridian/lib/harness/workspace_projection.py`.
- **Exit criteria:**
  - Every in-scope harness launch path (including streaming/shared projection
    utilities) produces one `HarnessWorkspaceProjection`.
  - Launch assembly composes workspace projections without harness-specific
    branches inside the domain-core pipeline delivered by R06.
  - Claude, Codex, and OpenCode all reach the same launch seam through the
    interface even though their transport mechanisms differ.
  - Explicit CLI `--add-dir` stays first under first-seen dedupe.
  - Primary launches using `MERIDIAN_HARNESS_COMMAND` surface
    `unsupported:harness_command_bypass` instead of pretending workspace roots
    were applied through the normal adapter path.
  - OpenCode day-1 support is delivered through native file-tool access, not an
    MCP side channel.

## R06 — Consolidate launch composition into a typed pipeline (3 driving adapters → factory → 2 executors)

This R06 supersedes the prior hexagonal-shell version. The architecture frame
(3 driving adapters, 1 factory, 2 executors, 3 driven adapters) is unchanged
— what changes is the *inside* of the factory: a typed pipeline driven by a
raw `SpawnRequest` input, instead of a `PreparedSpawnPlan` containing
already-resolved policy/permission/command outputs. See `decisions.md` D19
for the redesign rationale, `design/architecture/launch-core.md` for the
observational architecture, and `reviews/r06-retry-*.md` for the four
convergent reviews that drove the redesign.

- **Type:** prep refactor (blocks R05)

- **Why:** The first R06 implementation produced a hexagonal *shell* —
  `build_launch_context()` exists; `LaunchContext` is a sum type — but the
  *core* did not land. The factory accepts `PreparedSpawnPlan` whose
  `ExecutionPolicy` already carries resolved `PermissionConfig` and live
  `PermissionResolver` (`src/meridian/lib/ops/spawn/plan.py:9-21`). Every
  driving adapter must therefore call `resolve_policies` and
  `resolve_permission_pipeline` *before* it can construct factory input,
  which means composition still lives in drivers
  (`src/meridian/lib/launch/plan.py:234-334`,
  `src/meridian/lib/ops/spawn/prepare.py:202-328`,
  `src/meridian/lib/app/server.py:286-351`,
  `src/meridian/cli/streaming_serve.py:65`). The CI `rg`-count guards pass
  while the centralization invariant they were meant to protect is
  structurally false. The correctness review enumerated 14 concrete
  evasion patterns the script cannot catch
  (`reviews/r06-retry-correctness.md §7`).

  R06 is rewritten so the factory accepts raw `SpawnRequest` and runs an
  explicit named pipeline that owns every composition stage. Verification
  swaps from heuristic `rg` counts to a CI-spawned `@reviewer` architectural
  drift gate plus deterministic behavioral factory tests. The structural
  patterns (one builder per concern, driven port without mechanism leak,
  one fork owner, one bypass owner, one observation path) become honest
  through the type system and behavior, not through grep.

- **Architecture:**

  ```
  Primary launch ─┐
                   │
  Worker         ─┼──▶ build_launch_context(SpawnRequest, runtime, *, dry_run)
                   │             │
  App streaming  ─┘             │  pipeline:
                                 │  ├── (bypass branch — sole owner)
  Dry-run preview ───────────────┤  ├── resolve_policies()
                                 │  ├── resolve_permission_pipeline()
                                 │  ├── compose_prompt()
                                 │  ├── build_resolved_run_inputs()
                                 │  ├── materialize_fork()                ← gated by dry_run
                                 │  ├── resolve_launch_spec_stage()
                                 │  ├── apply_workspace_projection()      ← A04 seam
                                 │  ├── build_launch_argv()
                                 │  └── build_env_plan(env_additions=...)
                                 ▼
                           LaunchContext
                          (Normal | Bypass)
                                 │
                                 ▼
                     ┌── Primary executor (PTY/Popen)
                     └── Async subprocess executor
                                 │
                                 ▼
                          LaunchOutcome
                                 │
                                 ▼
                  driving adapter: harness.observe_session_id(...)
                                 │
                                 ▼
                          LaunchResult
  ```

  - **Domain core (`launch/context.py`)** — the factory orchestrates the
    pipeline above. Bypass branch lives inside the factory as the sole owner
    (`_build_bypass_context()`); the previous duplication between
    `launch/__init__.py` and `launch/context.py` collapses. Stages are
    composed in a fixed order; each stage has one named function in one
    owned file. The factory accepts `dry_run: bool` to gate the
    side-effect stage (`materialize_fork`). All other stages are
    side-effect-free except for bounded reads of profile/skill/session
    state already documented in the prior R06.

  - **3 driving adapters — same names, different responsibility:**
    1. **Primary launch** (`launch/plan.py` → `launch/process.py`) —
       constructs `SpawnRequest` and calls `build_launch_context()`. Does not
       call `resolve_policies`, `resolve_permission_pipeline`,
       `adapter.resolve_launch_spec`, `adapter.build_command`, or
       `adapter.fork_session` directly. Two capture modes (PTY / Popen)
       remain on the executor side; both consume `LaunchContext` and produce
       `LaunchOutcome`.
    2. **Background worker** (`ops/spawn/prepare.py` → `ops/spawn/execute.py`)
       — `prepare.py` constructs `SpawnRequest` and persists it; the
       persisted artifact replaces today's `PreparedSpawnPlan`. `execute.py`
       reads the persisted `SpawnRequest`, creates the spawn row, then calls
       `build_launch_context(..., dry_run=False)`. **Fork materialization
       happens after the spawn row exists, in every driver.** Dry-run
       preview goes through `build_launch_context(..., dry_run=True)`.
    3. **App streaming HTTP** (`app/server.py`) — constructs `SpawnRequest`,
       creates the spawn row, then calls `build_launch_context(..., dry_run=False)`.
       `TieredPermissionResolver` is no longer constructed here.

  - **Driven adapters** — `harness/claude.py`, `harness/codex.py`,
    `harness/opencode.py`. Receive `NormalLaunchContext`. Implement
    `observe_session_id()` (currently dead protocol slot). Permission-flag
    projection logic moves out of `harness/adapter.py` (port contract module)
    into each adapter (closes the structural review's "port leaks
    mechanism" finding).

  - **2 executors** — primary foreground (PTY/Popen capture-mode branch,
    primary launch only) and async subprocess_exec (worker + app streaming
    share). Executors return `LaunchOutcome` (raw exit_code, child_pid,
    captured PTY stdout); the driving adapter then calls
    `harness.observe_session_id(launch_context=..., launch_outcome=...)`
    once and assembles `LaunchResult`. The old
    `extract_latest_session_id()` path in
    `src/meridian/lib/launch/session_ids.py` is deleted.

- **DTO reshape (load-bearing):**

  Four user-visible types after R06 (one added in convergence-2 to carry
  runtime-injected context that is not user-input):

  - **`SpawnRequest`** (currently dead at `src/meridian/lib/harness/adapter.py:150`)
    — frozen pydantic model, fully serializable, no `arbitrary_types_allowed`.
    All `Path` values are stored as `str` to keep round-trip JSON-safe
    without custom encoders. Carries:
    - **prompt** (str), **model** (model ref str), **harness** (harness id),
      **agent** (agent ref str | None), **skills** (tuple of refs).
    - **extra_args** (tuple[str, ...]), **mcp_tools** (tuple[str, ...]).
    - **sandbox** (sandbox tier), **approval** (approval mode),
      **allowed_tools** (tuple[str, ...]), **disallowed_tools**
      (tuple[str, ...]), **autocompact** (bool).
    - **effort** (str | None) — model reasoning-effort override (Codex
      `-c model_reasoning_effort=...`).
    - **retry** (`RetryPolicy` nested, frozen) carrying
      `max_retries: int`, `retry_delay_secs: float`,
      `retryable_classes: tuple[str, ...]`. Execution-budget fields
      (`timeout_secs`, `kill_grace_secs`) live on a sibling
      `ExecutionBudget` nested model — both nested under `SpawnRequest.budget`
      to keep `RetryPolicy` faithful to its name.
    - **session** (`SessionRequest` nested, frozen) carrying
      `continue_chat_id: str | None`,
      `requested_harness_session_id: str | None`,
      `continue_fork: bool`,
      `source_execution_cwd: str | None`,
      `forked_from_chat_id: str | None`,
      **`continue_harness: str | None`** (parent harness id when continuing
      across harnesses),
      **`continue_source_tracked: bool`** (whether parent session was tracked
      by meridian),
      **`continue_source_ref: str | None`** (parent spawn-id or session ref
      for diagnostics). All eight fields preserve current behavior.
    - **context_from** (tuple[str, ...]) — raw context source refs (parent
      spawn ids, chat ids); resolution to file paths happens inside the
      factory and lives on `ResolvedRunInputs.context_from_resolved`.
    - **reference_files** (tuple[str, ...] of str paths),
      **template_vars** (dict[str, str], JSON-safe),
      **agent_metadata** (dict[str, str], JSON-safe),
      **work_id_hint** (str | None).

    **Constructed by every driving adapter and only by them.**

  - **`LaunchRuntime`** (new, runtime-injected context) — frozen
    pydantic model. Carries values that are not user-input but are needed by
    the factory to compose correctly:
    - `launch_mode: Literal["primary", "background"]` — discriminator
      consumed by driven adapters today via `SpawnParams.interactive`.
      Set by the driving adapter at construction time; primary launch sets
      `"primary"`, worker and app-streaming set `"background"`.
    - `unsafe_no_permissions: bool` — set true when the operator passed
      `--allow-unsafe-no-permissions`. Routes
      `resolve_permission_pipeline()` to use
      `UnsafeNoOpPermissionResolver`. Removes the previous app-streaming
      driver-side override (`app/server.py:~300`).
    - `debug: bool` — debug-mode flag used by background-worker telemetry
      paths (`BackgroundWorkerParams.debug` today).
    - `harness_command_override: str | None` — value of
      `MERIDIAN_HARNESS_COMMAND` if set; consumed only by
      `_build_bypass_context()`.
    - `report_output_path: Path` — observation channel for the spawn's
      `report.md`.
    - `state_paths: StatePaths`, `project_paths: ProjectPaths` — read
      models for stage logic that needs filesystem locations.
    `LaunchRuntime` is constructed by every driving adapter and only by
    them. It is **not persisted** by the worker; `execute.py` reconstructs
    it locally from the spawn row + environment.

  - **`LaunchContext = NormalLaunchContext | BypassLaunchContext`** (kept
    from current design, frozen, all-required) — executor input.
    - `NormalLaunchContext`: argv, env, child_cwd, spec, run_inputs
      (renamed from `run_params`), perms (live `PermissionResolver`),
      report_output_path, harness_adapter ref, **`warnings:
      tuple[CompositionWarning, ...]`** (composition-stage findings;
      replaces today's `PreparedSpawnPlan.warning` channel).
    - `BypassLaunchContext`: argv, env, child_cwd, **`warnings:
      tuple[CompositionWarning, ...]`**.
    `CompositionWarning` is a frozen pydantic model with `code: str`,
    `message: str`, optional `detail: dict[str, str]`. Pipeline stages
    append to a builder-local list; the factory freezes the tuple at
    return time. Drivers surface `warnings` to `SpawnActionOutput.warning`
    and to `meridian config show`/`doctor` diagnostics where applicable.

  - **`LaunchResult`** — exit_code, child_pid, session_id (populated by
    `observe_session_id()`).

  Two factory-internal types:

  - **`ResolvedRunInputs`** — renamed from `SpawnParams`. Constructed only
    inside `build_launch_context()` by `build_resolved_run_inputs()`.
    Carries skills-resolved-to-paths, **context_from_resolved** (file
    paths), continuation ids, appended prompts, report paths, prompt
    composition outputs. Driving adapters never see or construct this
    type. `NormalLaunchContext` exposes it as `run_inputs` for executor
    use only — it is readable but not reconstructable by drivers.
  - **`LaunchOutcome`** — executor → driving-adapter handoff. Raw exit_code,
    child_pid, optional captured PTY stdout. Replaces the implicit return
    contract of today's executors. **Drivers MUST NOT inspect
    `captured_stdout` directly** — session-ID parsing is the adapter's
    job inside `observe_session_id()`.

  **Deleted types:** `PreparedSpawnPlan`, `ExecutionPolicy`,
  `SessionContinuation` (top-level — folded into `SpawnRequest.session`
  with all eight fields preserved), `ResolvedPrimaryLaunchPlan`,
  `SpawnParams` (the user-facing form; renamed to factory-internal
  `ResolvedRunInputs`). The previously sketched `RuntimeContext`
  unification stays in scope: one `RuntimeContext` in `core/context.py`;
  `launch/context.py` imports it.

  Type ladder count: **7 named types with one-sentence purposes (4
  user-visible DTOs + `CompositionWarning` auxiliary + 2
  factory-internal types)**. The count grew by one over the
  convergence-1 sketch because hiding runtime-injected context inside
  `SpawnRequest` would have made `SpawnRequest` not honestly user-input.

- **Pipeline stages — owners, signatures, single-callsite invariant:**

  Each stage has one named function in one owned file. **No re-export
  shells.** The factory is the sole caller of every stage.

  - `launch/policies.py` — owns `resolve_policies(request, project_paths) ->
    ResolvedPolicies`. Stage logic moves here from `launch/resolve.py:230-329`;
    `resolve.py` keeps lower-level config/profile/skill/model resolution
    helpers that `policies.py` calls.
  - `launch/permissions.py` — owns `resolve_permission_pipeline(*, sandbox,
    allowed_tools, disallowed_tools, approval) -> tuple[PermissionConfig,
    PermissionResolver]`. Stage logic moves here from
    `safety/permissions.py:292`; `safety/permissions.py` keeps the
    resolver class and lower-level helpers.
  - `launch/prompt.py` — already exists with composition logic
    (`launch/prompt.py:63-318`). Becomes the sole composer of
    `compose_prompt(request, policies, harness) -> ComposedPrompt`. No
    duplication in drivers.
  - `launch/run_inputs.py` (new) — owns `build_resolved_run_inputs(...)
    -> ResolvedRunInputs`. Aggregates outputs of policies + permissions +
    composed prompt into the factory-internal type.
  - `launch/fork.py` — owns `materialize_fork(*, adapter, run_inputs,
    dry_run) -> ResolvedRunInputs` (already exists at
    `src/meridian/lib/launch/fork.py`; single-owner enforced by deleting
    the inline copy at `ops/spawn/prepare.py:296-311`).
  - `launch/command.py` — repurposed and split into two stages so the A04
    workspace-projection seam is reachable between them:
    - `resolve_launch_spec_stage(adapter, run_inputs, perms) ->
      ResolvedLaunchSpec` — **sole** call site for
      `adapter.resolve_launch_spec`.
    - `apply_workspace_projection(adapter, spec, run_inputs, runtime) ->
      tuple[ResolvedLaunchSpec, HarnessWorkspaceProjection]` — **sole**
      call site for `adapter.project_workspace`. Returns the (possibly
      extended) spec plus the projection object whose `env_additions`
      and `diagnostics` flow downstream.
    - `build_launch_argv(adapter, spec, run_inputs) -> tuple[str, ...]`
      — **sole** call site for `adapter.build_command`. Consumes the
      projection-extended spec.
    The legacy `build_launch_env` wrapper is deleted (subsumed by
    `build_env_plan`). The `MERIDIAN_HARNESS_COMMAND` parsing moves
    entirely into `launch/context.py:_build_bypass_context()`.
  - `launch/env.py` — owns `build_env_plan(*, adapter, run_inputs,
    permission_config, runtime_overrides, base_env, projection_env_additions)
    -> Mapping[str, str]`. Sole owner of child env construction;
    `build_harness_child_env` becomes an internal helper or is folded in.
    `projection_env_additions` is the channel A04's OpenCode
    `OPENCODE_CONFIG_CONTENT` flows through.

  **Placeholder module decisions:**

  | Module | Today | New owner |
  |---|---|---|
  | `launch/policies.py` | re-export shell | OWN: `resolve_policies` definition |
  | `launch/permissions.py` | re-export shell | OWN: `resolve_permission_pipeline` definition |
  | `launch/runner.py` | empty placeholder | DELETE |
  | `launch/command.py` | dead `build_launch_env` + bypass parsing | OWN: `resolve_launch_spec_stage`, `apply_workspace_projection`, `build_launch_argv` (split so A04's projection seam fits between spec resolution and argv build); `build_launch_env` deleted; bypass moved to `context.py` |
  | `launch/fork.py` | correct, single function | KEEP; enforce single-owner by deleting `prepare.py:296-311` inline copy |
  | `launch/session_ids.py` | old extractor still in use | DELETE; observation moves into adapter `observe_session_id()` |

- **Driven port cleanup:**

  Move concrete permission-flag projection logic out of
  `src/meridian/lib/harness/adapter.py:41-121` (port contract module) into
  each driven adapter. `adapter.py` keeps protocol declarations only
  (`HarnessCapabilities`, `RunPromptPolicy`, `SpawnRequest`,
  `HarnessAdapter`, `SubprocessHarness`, etc.). Each adapter
  (`harness/claude.py`, `harness/codex.py`, `harness/opencode.py`)
  implements its own permission-flag projection inside `env_overrides()` /
  `build_command()` as appropriate.

- **Single-owner constraints (named in invariants prompt):**

  | Concern | Today (split) | Sole owner after R06 |
  |---|---|---|
  | Bypass dispatch | `launch/__init__.py:65-77` (dry-run preview) + `launch/context.py:153-173` (runtime) | `launch/context.py:_build_bypass_context()` — preflight runs inside this branch so dry-run argv = runtime argv (closes correctness review D11) |
  | Fork materialization | `launch/fork.py:7-34` + inline `ops/spawn/prepare.py:296-311` | `launch/fork.py:materialize_fork` only |
  | `MERIDIAN_HARNESS_COMMAND` resolution | `context.py:153` + `launch/__init__.py` + `command.py:53` | `launch/context.py:_build_bypass_context()` |
  | Adapter `resolve_launch_spec` callsite | factory + `app/server.py:338` + drivers | `launch/command.py:resolve_launch_spec_stage()` |
  | Adapter `project_workspace` callsite | not yet wired (R05 target) | `launch/command.py:apply_workspace_projection()` |
  | Adapter `build_command` callsite | factory follow-up + `process.py:351` + multiple drivers | `launch/command.py:build_launch_argv()` |
  | Adapter `seed_session` and `filter_launch_content` callsites | scattered driver calls (`launch/plan.py:178-213`) | inside `compose_prompt()` / `build_resolved_run_inputs()`; never called by drivers |
  | `UnsafeNoOpPermissionResolver` dispatch | `app/server.py:~300` (driver) | `launch/permissions.py:resolve_permission_pipeline()` branches on `runtime.unsafe_no_permissions` |
  | Adapter `fork_session` callsite | `launch/fork.py` + `prepare.py:305` | `launch/fork.py:materialize_fork()` |
  | `TieredPermissionResolver` construction | `app/server.py:316`, `cli/streaming_serve.py:85`, drivers | `launch/permissions.py:resolve_permission_pipeline()` |
  | Session-ID observation | declared on protocol but no impls; `extract_latest_session_id` still in executors | per-adapter `observe_session_id()` (claude/codex/opencode); driving adapter calls once post-execution; `launch/session_ids.py` deleted |
  | `RuntimeContext` type | two types in `launch/context.py:42` and `core/context.py:13` | one type in `core/context.py` |
  | Child cwd creation | helper called from multiple sites including pre-row contexts | inside the factory after spawn row exists |

- **Fork transaction ordering (closes correctness review D4–D7):**

  The fork is a side effect against external Codex SQLite state. R06
  enforces fork-after-row in every driver:

  1. **Worker prepare phase** (`ops/spawn/prepare.py`) persists `SpawnRequest`
     only. **Does not call `materialize_fork`.** The persisted artifact is
     a `SpawnRequest` JSON blob, not a `PreparedSpawnPlan`.
  2. **Worker execute phase** (`ops/spawn/execute.py`) reads the persisted
     `SpawnRequest`, creates the spawn row (already in current code), then
     calls `build_launch_context(..., dry_run=False)` which materializes
     the fork. Spawn row exists before fork.
  3. **Primary path** (`launch/process.py`) creates the spawn row at line
     306 before calling `build_launch_context()` at line 328 (already
     correct in current code). Behavioral test asserts ordering.
  4. **App streaming path** (`app/server.py`) creates the spawn row before
     calling `build_launch_context()`. Behavioral test asserts ordering.
  5. **Streaming-runner fallback** (`launch/streaming_runner.py`) currently
     builds context before fallback `start_spawn` when row is missing
     (correctness review D6). R06 changes `execute_with_streaming` to
     **require** a precondition: the spawn row must exist. The fallback
     creates the row first, then calls the factory. If the row cannot be
     created, the call fails fast before any factory work.
  6. **Child cwd creation** (correctness review D7): `resolve_child_execution_cwd`
     + `mkdir` happens inside the factory, after the spawn row exists, not
     in helper code that any driver could call preemptively. The
     `launch/cwd.py` helper signature changes so callers cannot create the
     cwd without supplying the spawn id of an existing row.

  **Failure semantics:** if `materialize_fork` raises after the spawn row
  exists, the driving adapter marks the spawn row `failed` with reason
  `fork_materialization_error` and re-raises. The Codex SQLite copy is not
  rolled back (codex rollouts are append-only with content-addressed
  naming; orphan rollouts on the codex side are tolerated). The
  orphan-fork window is reduced to "spawn row marked failed with
  identifiable reason" — operators can find and clean up via the
  documented reason code.

- **Session-ID adapter seam (`observe_session_id()`) — actually wired:**

  - Per-adapter `observe_session_id(*, launch_context, launch_outcome) ->
    str | None` implementations land in `harness/claude.py`,
    `harness/codex.py`, `harness/opencode.py`. Existing observation
    mechanisms move into these methods. The contract is uniform across
    adapters: `observe_session_id` is the adapter's per-launch
    observation method, which **may inspect either** `launch_outcome`
    fields **or** per-launch state owned by objects reachable from
    `launch_context` (e.g., the `connection` held by an HTTP/WS adapter
    for the lifetime of this launch). It MUST NOT read or write
    adapter-instance singleton state shared across launches. The mechanism
    differs by adapter, but the contract is one:
    - **Claude** reads `launch_outcome.captured_stdout` (PTY-captured
      bytes) and parses the latest session id. PTY mode populates this
      field; Popen mode leaves it `None` and `observe_session_id` returns
      `None` (issue #34 covers the filesystem-polling fix).
    - **Codex** reads `connection.session_id` set during WebSocket
      bootstrap (`connections/codex_ws.py:190,270`). The `connection`
      is owned by this launch and reachable through `launch_context`;
      `launch_outcome` is unused.
    - **OpenCode** reads `connection.session_id` set during session
      creation (`connections/opencode_http.py:137,166`). Same pattern as
      Codex.
    The prior review's "not a parser" framing is superseded — parsing is
    legitimate when the source is `launch_outcome` (a per-launch value)
    rather than adapter-instance state. The closed concern was shared
    mutable state on the adapter; that remains forbidden.
  - Each executor returns `LaunchOutcome` only.
  - The driving adapter calls `harness.observe_session_id(...)` exactly
    once after the executor returns, then assembles `LaunchResult`. The
    spawn-row update for `harness_session_id` happens with this value
    (closes correctness review D10 — observation before terminal finalize).
  - `launch/session_ids.py:16-54` (`extract_latest_session_id`) and any
    inline executor scrape paths in `launch/process.py:451-476` and
    `launch/streaming_runner.py:859-883` are deleted.

  **Known limitation preserved:** Popen-fallback session-ID observability
  remains absent until GitHub issue #34 swaps mechanism to filesystem
  polling. R06 lands the seam; the implementation swap is separate.

- **Verification approach (replaces `rg`-count CI guards):**

  `scripts/check-launch-invariants.sh` is **deleted** in this refactor. The
  `check-launch-invariants` step is removed from
  `.github/workflows/meridian-ci.yml`. Verification is three layers:

  **1. Behavioral factory tests** (`tests/launch/test_launch_factory.py`,
  new) — pin the load-bearing invariants directly. Required tests:

  - `test_factory_resolves_permissions_from_raw_inputs` — given a
    `SpawnRequest` with sandbox/approval/allowed/disallowed_tools, the
    returned `NormalLaunchContext.perms` reflects the policy. **Asserts a
    driver does not need to construct any `PermissionResolver` to call the
    factory.**
  - `test_factory_dry_run_argv_matches_runtime_argv` — for the same
    `SpawnRequest`, `dry_run=True` and `dry_run=False` produce identical
    argv (preflight runs in both paths). Closes correctness review D11.
  - `test_factory_dry_run_skips_fork_materialization` — given a request
    that would normally fork, `dry_run=True` returns context with original
    session id and no `fork_session()` call (mock the adapter and assert).
  - `test_factory_bypass_dispatch_single_owner` — when
    `MERIDIAN_HARNESS_COMMAND` is set in `runtime`, the factory returns
    `BypassLaunchContext` with preflight-expanded passthrough args
    included in `argv`.
  - `test_factory_returns_normal_context_with_required_fields` —
    `NormalLaunchContext` fields are all required at construction
    (frozen, no `None` defaults on load-bearing fields).
  - `test_observe_session_id_dispatched_through_adapter` — given a fake
    adapter that records `observe_session_id` calls, assert it is called
    exactly once after the executor returns `LaunchOutcome`, and the
    returned `LaunchResult.session_id` equals what the adapter returned.
  - `test_fork_after_spawn_row_in_worker` — wire a fake spawn-store +
    fake adapter; assert `start_spawn` returns before `fork_session` is
    invoked when worker `execute.py` calls the factory.
  - `test_streaming_runner_requires_spawn_row_precondition` — calling
    `execute_with_streaming` without a created spawn row raises a
    precondition error before any factory work runs.
  - `test_persisted_spawn_request_round_trips` — `SpawnRequest` →
    `model_dump_json` → `model_validate_json` produces an equal value
    with no live-object fields.
  - `test_no_pre_resolved_permission_resolver_in_persisted_artifact` —
    inspect the JSON form of a persisted `SpawnRequest`; assert no field
    name carries a serialized resolver/config blob.
  - `test_child_cwd_not_created_before_spawn_row` (closes correctness
    review D7) — wire a fake spawn-store and a temp-dir fake `child_cwd`
    helper; assert `start_spawn` returns before `mkdir`/`resolve_child_execution_cwd`
    is invoked when any driver path reaches the factory. Includes the
    streaming-runner fallback path.
  - `test_composition_warnings_propagate_to_launch_context` — register a
    pipeline stage that appends a `CompositionWarning`; assert the
    returned `NormalLaunchContext.warnings` contains it in order, and
    that the driver-side `SpawnActionOutput.warning` channel observes
    the same content. Replaces the deleted `PreparedSpawnPlan.warning`
    channel.
  - `test_workspace_projection_seam_reachable` (also exercises A04) —
    register a fake adapter whose `project_workspace()` returns a
    sentinel `extra_args` value; assert the resulting argv contains the
    sentinel after `build_launch_argv()`, proving the
    `apply_workspace_projection` stage runs between spec resolution and
    argv build.
  - `test_unsafe_no_permissions_dispatches_through_factory` — set
    `runtime.unsafe_no_permissions = True`; assert
    `NormalLaunchContext.perms` is an `UnsafeNoOpPermissionResolver`
    instance and the driving adapter never called the resolver
    constructor itself.
  - `test_session_request_carries_all_eight_continuation_fields` —
    given a `SessionRequest` with all eight fields populated,
    round-trip through `SpawnRequest.model_dump_json` /
    `model_validate_json`; assert no field is lost.

  **2. CI-spawned `@reviewer` as architectural drift gate.** A new file
  `.meridian/invariants/launch-composition-invariant.md` declares the
  semantic invariants in prose. A new step in
  `.github/workflows/meridian-ci.yml` runs only on PRs that touch files
  under `src/meridian/lib/(launch|harness|ops/spawn|app)/`:

  ```bash
  meridian spawn -a reviewer \
    --prompt-file .meridian/invariants/launch-composition-invariant.md \
    -f $(git diff --name-only origin/main HEAD | grep -E '^src/meridian/lib/(launch|harness|ops/spawn|app)/') \
    -m <cheap-mini-or-flash-variant-from-meridian-models-list>
  ```

  The reviewer reads the diff against the invariant prompt, returns
  `pass | fail` with file:line violations, and the CI step blocks merge on
  `fail`. The full prompt is drafted in
  `design/launch-composition-invariant.md` for review under this design
  package; implementation copies it to
  `.meridian/invariants/launch-composition-invariant.md`. Summary of
  invariants asserted (full text in the design-package draft):

  - **Composition centralization** — composition lives only inside
    `build_launch_context()` and its named pipeline stages.
  - **Driving-adapter prohibition list** — no driving-adapter file
    (`launch/plan.py`, `launch/process.py`, `ops/spawn/prepare.py`,
    `ops/spawn/execute.py`, `app/server.py`, `cli/streaming_serve.py`)
    calls `resolve_permission_pipeline`, `TieredPermissionResolver`,
    `UnsafeNoOpPermissionResolver`, `adapter.resolve_launch_spec`,
    `adapter.project_workspace`, `adapter.build_command`,
    `adapter.fork_session`, `adapter.seed_session`,
    `adapter.filter_launch_content`, or `build_harness_child_env`
    directly.
  - **Single owners** — bypass dispatch only in `_build_bypass_context()`;
    fork materialization only in `materialize_fork()`; child cwd
    creation only inside the factory after the spawn row exists.
  - **Observation path** — `observe_session_id` is called by exactly one
    path (driving adapter after executor returns `LaunchOutcome`); no
    adapter-instance singleton state holds session ids.
  - **DTO discipline** — no `PreparedSpawnPlan`-style pre-composed DTO is
    reintroduced under a different name; persisted artifact is plain
    `SpawnRequest` JSON without `arbitrary_types_allowed`; warnings flow
    through `LaunchContext.warnings`, not through DTO sidechannels.
  - **Stage modules own real logic** — `launch/policies.py`,
    `launch/permissions.py`, `launch/fork.py`, `launch/env.py`,
    `launch/command.py`, `launch/run_inputs.py` are not re-export shells.
  - **Driven port keeps shape only** — `harness/adapter.py` declares
    contracts only; no concrete permission-flag projection logic.
  - **Workspace projection seam reachable** — `apply_workspace_projection`
    runs between `resolve_launch_spec_stage` and `build_launch_argv`
    inside the factory; A04's `project_workspace()` adapter method is
    called from this stage and only this stage.

  Reviewer model selection follows `agent-staffing` guidance: cheap
  `mini`/`flash` variant for routine drift detection, escalate to default
  reviewer on PRs that materially restructure the protected surface. The
  invariant prompt is version-controlled and updated as part of any
  legitimate change to the declared invariants.

  **3. pyright + ruff + pytest** remain the correctness gate. The
  drift-gate reviewer sits beside them, not in place of them. The
  behavioral tests are normal pytest tests run by the existing pytest CI
  step.

- **Scope (file list — not a how-to plan):**

  *Domain core:*
  - `src/meridian/lib/launch/context.py` — rewrite factory body to consume
    `SpawnRequest`; bypass branch becomes sole owner; remove pre-resolved
    `PreparedSpawnPlan` parameter.
  - `src/meridian/lib/launch/policies.py` — own `resolve_policies` definition.
  - `src/meridian/lib/launch/permissions.py` — own `resolve_permission_pipeline`.
  - `src/meridian/lib/launch/fork.py` — keep; single-owner enforced.
  - `src/meridian/lib/launch/env.py` — own `build_env_plan` as the sole env builder.
  - `src/meridian/lib/launch/command.py` — own `project_launch_command`; delete `build_launch_env`; remove bypass parsing.
  - `src/meridian/lib/launch/run_inputs.py` — new; owns `build_resolved_run_inputs`.
  - `src/meridian/lib/launch/runner.py` — delete.
  - `src/meridian/lib/launch/session_ids.py` — delete.
  - `src/meridian/lib/launch/__init__.py` — collapse dry-run preview duplication into the factory; primary entry calls factory.

  *Driving adapters:*
  - `src/meridian/lib/launch/plan.py` — `resolve_primary_launch_plan` delegates composition to the factory; `ResolvedPrimaryLaunchPlan` is deleted.
  - `src/meridian/lib/launch/process.py` — consumes `LaunchContext`; stops calling `adapter.build_command` post-factory; no rebuild of `run_params` after planning.
  - `src/meridian/lib/ops/spawn/prepare.py` — `build_create_payload` constructs and persists `SpawnRequest`; no permission resolution; no fork materialization; no preview command construction outside the factory.
  - `src/meridian/lib/ops/spawn/execute.py` — reads persisted `SpawnRequest`, creates spawn row, calls factory; the independent `resolve_permission_pipeline()` call at line 861 is removed.
  - `src/meridian/lib/app/server.py` — constructs `SpawnRequest`, creates row, calls factory; no `TieredPermissionResolver` construction; no `adapter.resolve_launch_spec` direct call; uses exhaustive `match` over `LaunchContext`.
  - `src/meridian/cli/streaming_serve.py` — folds into shared `execute_with_streaming` path; constructs `SpawnRequest`; no hardcoded `TieredPermissionResolver(config=PermissionConfig())`.

  *Driven adapters:*
  - `src/meridian/lib/harness/adapter.py` — keep protocol contracts only; remove permission-flag projection logic; restore `SpawnRequest` to load-bearing.
  - `src/meridian/lib/harness/claude.py`, `harness/codex.py`, `harness/opencode.py` — each implements `observe_session_id()` (relocate existing scrape/connection logic). Permission-flag projection logic moves in from `adapter.py`.

  *Deletions:*
  - `src/meridian/lib/ops/spawn/plan.py` — `PreparedSpawnPlan`, `ExecutionPolicy`, `SessionContinuation` deleted; replaced by `SpawnRequest` + factory composition.
  - `src/meridian/lib/launch/streaming_runner.py:389` — `run_streaming_spawn` and its export deleted (already in original R06; preserved here).
  - `src/meridian/lib/streaming/spawn_manager.py:180` — `SpawnManager.start_spawn` unsafe-resolver fallback deleted; `spec` parameter becomes required `LaunchContext`.
  - `scripts/check-launch-invariants.sh` — deleted.
  - `.github/workflows/meridian-ci.yml` — `check-launch-invariants` step removed; `architectural-drift-gate` step added.

  *New artifacts:*
  - `.meridian/invariants/launch-composition-invariant.md` — invariant prompt for the drift-gate reviewer.
  - `tests/launch/test_launch_factory.py` — behavioral factory tests.

- **Test blast radius** (enumerate before refactoring):
  ```
  rg -l "RuntimeContext|prepare_launch_context|LaunchContext|build_launch_context\
  |build_launch_env|build_harness_child_env|PreparedSpawnPlan|resolve_policies\
  |resolve_permission_pipeline|SpawnParams|merge_env_overrides\
  |resolve_launch_spec|run_streaming_spawn|SpawnRequest|materialize_fork\
  |ExecutionPolicy|SessionContinuation|ResolvedPrimaryLaunchPlan\
  |observe_session_id|extract_latest_session_id" tests/
  ```
  Known impacted test files include at minimum:
  - `tests/exec/test_streaming_runner.py`
  - `tests/exec/test_depth.py`
  - `tests/exec/test_permissions.py`
  - `tests/test_launch_process.py`
  - `tests/test_app_server.py`
  - `tests/ops/test_spawn_prepare_fork.py`
  - `tests/harness/test_codex_fork_session.py`

  Tests added by R06:
  - `tests/launch/test_launch_factory.py` (the verification-layer 1 suite enumerated above)
  - `tests/launch/test_session_request_round_trip.py` — `SpawnRequest` JSON round-trip without `arbitrary_types_allowed`
  - `tests/harness/test_observe_session_id.py` — per-adapter observation contract
  - `tests/ops/spawn/test_fork_after_row.py` — worker ordering
  - `tests/cli/test_invariants_drift_gate.py` (optional, lightweight) — sanity check that the invariant prompt and CI step exist

  All identified tests must be updated in the same change set as the source
  refactor, not left as follow-up drift.

- **Suggested internal phasing** (the planner can rearrange; this is one
  honest sequencing):

  1. Make `SpawnRequest` load-bearing: define the full schema (currently
     dead at `harness/adapter.py:150`); add JSON round-trip test. No
     callers yet.
  2. Pipeline stage extraction: move `resolve_policies` into
     `launch/policies.py`, `resolve_permission_pipeline` into
     `launch/permissions.py`, `project_launch_command` into
     `launch/command.py`. Add behavioral factory test scaffolding.
  3. `build_resolved_run_inputs` aggregator + factory-internal
     `ResolvedRunInputs` rename.
  4. `build_launch_context` accepts `SpawnRequest` + `LaunchRuntime`;
     bypass branch becomes sole owner; preflight runs inside bypass for
     dry-run parity.
  5. `materialize_fork` single-owner enforcement (delete `prepare.py`
     inline copy); fork-after-row ordering tests.
  6. `observe_session_id` per-adapter implementations + executor
     `LaunchOutcome` return + driving-adapter assembly of `LaunchResult`.
     Delete `launch/session_ids.py`.
  7. Rewire each driving adapter: primary, then worker, then app streaming.
     Each transition a separate commit; behavioral tests gate.
  8. Delete `PreparedSpawnPlan`, `ExecutionPolicy`, `SessionContinuation`
     (top-level), `ResolvedPrimaryLaunchPlan`. Type ladder collapses.
  9. Delete `scripts/check-launch-invariants.sh`; add invariant prompt at
     `.meridian/invariants/launch-composition-invariant.md`; rewire CI.
  10. Driven port cleanup: move permission-flag projection out of
      `harness/adapter.py` into adapters.
  11. `RuntimeContext` unification (one type in `core/context.py`).

  Steps 1–3 land independently. Step 4 unblocks 5/6. Steps 7 land per
  driver and are gated by behavioral tests. Step 8 closes the type
  collapse. Steps 9–11 are cleanup that can land in parallel with each
  other but after the rewires complete.

- **Preserved divergences (not flattened by R06):**
  - Primary executor has two capture modes (PTY capture + direct Popen)
    driven by runtime environment. Both consume `LaunchContext`, produce
    `LaunchOutcome`. PTY enables session-ID scraping; Popen loses
    session-ID observability today. GitHub issue #34 tracks moving to
    filesystem polling.
  - Claude-in-Claude sub-worktree cwd stays as a `child_cwd` field on
    `NormalLaunchContext`, populated by the pipeline.
  - `ensure_claude_session_accessible` import behavior moves behind the
    adapter contract so the domain core does not import concrete harness
    modules.

- **Red flag (out of scope, filed separately):** Background workers
  serialize `allowed_tools` but drop `disallowed_tools`, then re-resolve
  permissions without the denylist (`ops/spawn/execute.py:82-103`,
  `execute.py:861-865`, `prepare.py:323-328`). This is a correctness bug
  in the permission pipeline, not an R06 composition concern. R06's
  `SpawnRequest` schema *includes* `disallowed_tools` so the bug becomes
  fixable as soon as the persistence path uses `SpawnRequest`; the
  follow-up fix lands as its own commit with its own test.

- **Out of scope (separate work items):**
  - GitHub issue #34 — Popen-fallback session-ID observability via
    filesystem polling. R06 lands the `observe_session_id()` adapter seam;
    the mechanism swap to filesystem polling is a separate change.
  - Claude session-accessibility symlinking (`p1878` Q5).
  - Removing dead legacy subprocess-runner code and clarifying misleading
    `_subprocess` filenames on shared projection utilities (issue #32).
