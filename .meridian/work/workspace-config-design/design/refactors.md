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

## R06 — Consolidate launch composition into a hexagonal core (3 driving adapters through one factory)

- **Type:** prep refactor (blocks R05)

- **Why:** Meridian launch composition today has multiple call sites that
  independently resolve policies, build permissions, construct env, and call
  `adapter.resolve_launch_spec()`. A feasibility probe (`p1893`) established
  that the honest architecture is **3 driving adapters** — not 1 and not 9.
  Not 1 because primary launch is a foreground process under meridian's
  control (PTY capture or direct Popen depending on environment), the
  background worker must be a detached one-shot subprocess that outlives the
  parent, and app-streaming keeps the manager in-process for the current
  REST/WS API shape — these are incompatible driver semantics. Not 9 because the previous enumeration mixed call locations
  inside the same adapter (e.g. `plan.py` + `process.py` + `command.py` are
  all internal to the primary launch driver) and counted two dead parallel
  implementations that R06 deletes:

  1. `launch/streaming_runner.py:389` (`run_streaming_spawn`) — a parallel
     implementation beside `execute_with_streaming` at line 742. It
     independently gets an adapter, calls `resolve_launch_spec()`, and runs
     its own `SpawnManager` lifecycle. Called only from
     `cli/streaming_serve.py:98`.
  2. `streaming/spawn_manager.py:180` (`SpawnManager.start_spawn`) — has an
     unsafe-resolver fallback that calls `resolve_launch_spec(SpawnParams(prompt=...),
     UnsafeNoOpPermissionResolver())` when callers omit `spec`. Post-R06 all
     callers hand in a resolved `LaunchContext`, making the fallback dead.

  Additionally, `SpawnParams` is not a user-input DTO — it carries resolved
  state (skills, session ids, appended system prompts, report paths). R06
  splits it into a user-facing `SpawnRequest` and a resolved `SpawnParams`
  (or successor) that only exists inside/after the factory.

  The user directive is to make drift structurally difficult. R06 establishes
  a hexagonal domain core with one factory so R05 has exactly one insertion
  point and future launch-touching features cannot compound the drift.
  Drift protection is enforced by heuristic CI guardrails (`rg`-based
  checks + Pyright exhaustiveness), not by mechanically impossible
  constraints — see exit criteria for known evasion modes.

- **Architecture:**

  ```
  Primary launch ─┐
                   │
  Worker         ─┼──▶ build_launch_context() ──▶ LaunchContext ──▶ executor ──▶ harness adapter ──▶ process
                   │    (driving port / factory)                     (PTY or async)  (driven port)
  App streaming  ─┘
                   │
  Dry-run        ─┘ (no executor; preview output)
  ```

  - **Domain core** — pipeline of composition stages. Contains the canonical
    `LaunchContext` sum type (`NormalLaunchContext | BypassLaunchContext`) plus
    exactly one builder per composition concern. The builders form a pipeline;
    `build_launch_context()` is the factory that runs the pipeline and returns
    a complete `LaunchContext`. Several stages read bounded configuration from
    disk as part of composition: `resolve_policies()` loads agent profiles and
    skills (`src/meridian/lib/launch/resolve.py:20,83`); env construction reads
    session state (`src/meridian/lib/launch/env.py:75`); Claude workspace
    projection reads `.claude/settings*.json`
    (`src/meridian/lib/harness/claude_preflight.py:78`). One stage —
    `materialize_fork()` — performs state-mutating I/O against the Codex
    session API and is marked explicitly. The factory's invariant is
    **centralization**, not purity: composition happens only in this pipeline.
  - **3 driving adapters** — each with a named architectural reason to exist:
    1. **Primary launch** (`launch/plan.py` → `launch/process.py`) — foreground
       process under meridian's control until exit. Has two capture modes:
       **PTY capture** (intended, when stdin/stdout are TTYs and output log
       path is configured): `pty.fork()` + `os.execvpe()`, harness sees a
       terminal, session-ID observability via adapter-owned scraping.
       **Direct Popen** (degraded fallback, when runtime lacks TTYs meridian
       can proxy): `subprocess.Popen().wait()`, session-ID observability lost
       on this path today. GitHub issue #34 tracks moving session-ID
       observation to filesystem polling, removing this degradation.
       Both paths consume the same `LaunchContext` and return the same
       `LaunchResult` contract.
    2. **Background worker** (`ops/spawn/prepare.py:build_create_payload` →
       `ops/spawn/execute.py`) — detached one-shot subprocess per spawn.
       `meridian spawn` forks a detached `python -m
       meridian.lib.ops.spawn.execute` process per spawn id; that process
       composes once, executes, writes its report, and exits. The
       architectural reason is **detached lifecycle** — the meridian parent
       can exit or crash without orphaning the spawn.
    3. **App streaming HTTP** (`app/server.py:268-365`) — in-process
       `SpawnManager` control channel. The REST/WS interface is structured
       around a manager held by the HTTP handler; `/inject` and `/interrupt`
       route through the same in-memory connection. The architectural reason
       is **current API shape**: composition happens at request time to keep
       the manager local. Meridian's separate `control.sock` +
       `spawn_inject` mechanism demonstrates out-of-process control is
       possible; moving app-streaming to queued exec + remote control is a
       separate refactor (out of scope for workspace-config-design).
  - **Driven adapters** — harness adapters (`harness/claude`, `harness/codex`,
    `harness/opencode`). Receive `NormalLaunchContext` and produce
    harness-specific output via `resolve_launch_spec()`,
    `observe_session_id()`, `project_workspace()`, `build_command()`, etc.
  - **2 executors** — primary foreground (PTY/Popen capture-mode branch,
    primary launch only) and async subprocess_exec (worker + app streaming
    share).
  - **1 preview caller** — dry-run (`spawn create --dry-run` and primary
    `--dry-run`) calls the factory for `composed_prompt` + `cli_command`
    preview output without executing.

- **Scope:**

  **1. Domain core (create/consolidate):**
  - `src/meridian/lib/launch/context.py` — becomes the home of
    `build_launch_context()`, the factory that orchestrates the pipeline and
    returns a `LaunchContext`. Contains the `NormalLaunchContext | BypassLaunchContext`
    sum type as frozen dataclasses with required fields at the type level.
  - One builder per pipeline stage, one file per stage:
    - `resolve_policies()` — in `launch/policies.py` (or successor from current
      `launch/resolve.py:230` policy resolution)
    - `resolve_permission_pipeline()` — in `launch/permissions.py` (or successor
      from current `safety/permissions.py:292` plus independent call at
      `ops/spawn/execute.py:861`)
    - `materialize_fork()` — in `launch/fork.py` (consolidating the two
      identical fork-materialization sites at `launch/process.py:68-105` and
      `ops/spawn/prepare.py:296-311`). Runs post-spec-resolution, pre-env.
      See "Fork continuation" under Preserved divergences.
    - `build_env_plan()` — in `launch/env.py` (consolidating current
      `build_launch_env()` at `launch/command.py:16` and
      `build_harness_child_env()` at `launch/env.py:185`)
    - `resolve_launch_spec()` — adapter-owned (already harness-implemented;
      called once from the factory)
  - `MERIDIAN_HARNESS_COMMAND` bypass: `build_launch_context()` runs policy +
    session resolution, then branches and returns `BypassLaunchContext` with
    concrete fields (`argv`, `env`, `cwd`). Bypass does not call spec
    resolution, workspace projection, or `build_harness_child_env`; it calls
    `inherit_child_env` instead. Current bypass split across
    `launch/plan.py:259-268` and `launch/command.py:53-57` collapses into the
    factory.
  - `src/meridian/lib/launch/context.py:42` and `src/meridian/lib/core/context.py:13`
    — the two `RuntimeContext` types unify into one. Load-bearing lever: two
    types cannot silently fork behavior.

  **2. Three driving adapters (route through factory):**

  Each driving adapter today composes independently. After R06, each
  constructs a `SpawnRequest` (user-facing args only), calls
  `build_launch_context()`, and hands the resulting `LaunchContext` to the
  appropriate executor:

  - **Primary launch:** `src/meridian/lib/launch/plan.py` +
    `src/meridian/lib/launch/process.py` + `src/meridian/lib/launch/command.py`
    — `resolve_primary_launch_plan()` delegates composition to
    `build_launch_context()` instead of duplicating it; the
    `MERIDIAN_HARNESS_COMMAND` short-circuit moves into the factory (returns
    `BypassLaunchContext`). `build_launch_env()` and `MERIDIAN_HARNESS_COMMAND`
    branch in `command.py` collapse into the domain-core pipeline.
    `run_harness_process()` consumes `LaunchContext` and stops rebuilding
    `run_params`/command after planning. Primary dry-run calls the factory
    and returns preview without executing.
  - **Background worker:** `src/meridian/lib/ops/spawn/prepare.py:169`
    (`build_create_payload`) + `src/meridian/lib/ops/spawn/execute.py` —
    `build_create_payload` becomes a thin caller that constructs
    `SpawnRequest` and calls `build_launch_context()`. The independent
    `resolve_permission_pipeline()` call at `execute.py:861` moves into the
    factory. Worker dry-run (`spawn create --dry-run`) calls the factory for
    preview.
  - **App streaming HTTP:** `src/meridian/lib/app/server.py:268-365` —
    currently builds `SpawnParams` and calls `adapter.resolve_launch_spec()`
    directly at line 338, constructs `TieredPermissionResolver` at line 316.
    After R06, constructs `SpawnRequest` (allowed) and calls
    `build_launch_context()` (required); hands `LaunchContext` to
    `SpawnManager` which uses async subprocess executor. `/inject` and
    `/interrupt` reach the same manager; composition does not happen there.

  **3. Driven adapters (no composition leakage):**
  - `src/meridian/lib/harness/claude.py`, `src/meridian/lib/harness/codex.py`,
    `src/meridian/lib/harness/opencode.py` — keep harness-specific translation
    only. Any composition logic currently inside harness modules (policy
    resolution, env building) moves to the domain core. Adapters accept
    `NormalLaunchContext`, not the sum.
  - Domain core imports from `harness/adapter.py` (abstract contract module)
    only. It does not import from `harness/claude`, `harness/codex`,
    `harness/opencode`, or `harness/projections`.

  **4. Deletions (dead parallel code):**
  - `src/meridian/lib/launch/streaming_runner.py:389` — delete
    `run_streaming_spawn()` and its export at line 1256. This function
    independently gets an adapter (line 419), calls
    `adapter.resolve_launch_spec(params, perms)` (line 420), runs its own
    `SpawnManager` lifecycle, and duplicates the `execute_with_streaming`
    path at line 742 which already uses `prepare_launch_context`.
  - `src/meridian/cli/streaming_serve.py:12,98` — fold streaming serve CLI
    into the shared `execute_with_streaming` path. The CLI constructs a
    `SpawnRequest` and calls `build_launch_context()` instead of calling
    `run_streaming_spawn`.
  - `src/meridian/lib/streaming/spawn_manager.py:180`
    (`SpawnManager.start_spawn`) — delete the unsafe-resolver fallback at
    lines 196-199 that calls `resolve_launch_spec(SpawnParams(prompt=...),
    UnsafeNoOpPermissionResolver())` when callers omit `spec`. Post-R06 all
    callers hand in a resolved `LaunchContext`; the `spec: ... | None = None`
    parameter becomes required.
  - `src/meridian/lib/app/server.py:316` — the direct
    `TieredPermissionResolver(config=permission_config)` construction moves
    inside the factory; the HTTP handler passes policy inputs, not a
    pre-resolved resolver.
  - `src/meridian/cli/streaming_serve.py:85` — the hardcoded
    `TieredPermissionResolver(config=PermissionConfig())` construction is
    deleted when this CLI is routed through the factory.

  **5. Type splits:**
  - `SpawnParams` (currently at `harness/adapter.py:147`) carries resolved
    execution state today (skills, session ids, appended system prompts,
    report paths). Split into:
    - `SpawnRequest` — user-facing args only (prompt, harness, model,
      approval, skills refs, workspace refs). Constructed by CLI/HTTP/app
      layers (the driving adapters).
    - `SpawnParams` (or renamed successor like `ResolvedLaunchInputs`) —
      resolved execution inputs, constructed only inside/after the factory.
      Carries skills-resolved-to-paths, continuation ids, appended prompts,
      report paths.
  - `RuntimeContext` unified to one type across the codebase.

- **Exit criteria:**

  Each invariant has an exact `rg` command and expected result. All `rg`
  checks are **heuristic guardrails** — they detect named-call-pattern drift
  but are evadable by aliasing, indirect dispatch, or reimplementation under
  different names. These checks are wired into CI via
  `scripts/check-launch-invariants.sh` (see scope addition §6 below).
  Reviewers must verify that builder calls use their canonical names in
  driving-adapter modules. A future AST-based enforcement upgrade is tracked
  separately.

  **Pipeline — one builder per concern (definition + sole-caller checks):**

  `resolve_policies`:
  - `rg "^def resolve_policies\(" src/` → exactly 1 match, in
    `src/meridian/lib/launch/policies.py`.
  - `rg "resolve_policies\(" src/ --type py` → matches only in
    `launch/policies.py` (definition) and `launch/context.py` (sole caller
    in factory). Zero matches in driving adapters.
  - **Heuristic limitations.** Evadable by: aliasing on import (`from
    policies import resolve_policies as rp`), indirect dispatch (`fn =
    resolve_policies; fn(...)`), or reimplementation under a different name.

  `resolve_permission_pipeline`:
  - `rg "^def resolve_permission_pipeline\(" src/` → 1 match, in
    `launch/permissions.py`.
  - `rg "resolve_permission_pipeline\(" src/ --type py` → matches only in
    `launch/permissions.py` (definition) and `launch/context.py` (sole
    caller in factory). Zero matches in driving adapters.
  - **Heuristic limitations.** Same aliasing/indirection evasion modes as
    `resolve_policies`. Additionally, `TieredPermissionResolver` construction
    could be duplicated under a different variable name.

  `materialize_fork`:
  - `rg "^def materialize_fork\(" src/` → 1 match, in `launch/fork.py`.
  - `rg "materialize_fork\(" src/ --type py` → matches only in
    `launch/fork.py` (definition) and `launch/context.py` (sole caller
    in factory). Zero matches in driving adapters.
  - **Heuristic limitations.** Same aliasing/indirection modes. Fork logic
    could also be reimplemented by directly calling `adapter.fork_session()`
    outside the pipeline.

  `build_env_plan`:
  - `rg "^def build_env_plan\(" src/` → 1 match, in `launch/env.py`.
  - `rg "build_env_plan\(" src/ --type py` → matches only in
    `launch/env.py` (definition) and `launch/context.py` (sole caller in
    factory). Zero matches in driving adapters.
  - **Heuristic limitations.** Same aliasing/indirection modes.

  `build_harness_child_env`:
  - `rg "^def build_harness_child_env\(" src/` → 1 match, in
    `launch/env.py`, called only from `build_env_plan()`.
  - `rg "build_harness_child_env\(" src/ --type py` → matches only in
    `launch/env.py` (definition + sole internal caller). Zero matches
    outside `launch/env.py`.
  - **Heuristic limitations.** Same aliasing/indirection modes. Env
    construction could be reimplemented by calling `inherit_child_env`
    or `os.environ` manipulation directly.

  **Plan Object — one sum type:**
  - `rg "^class NormalLaunchContext\b" src/` → 1 match.
  - `rg "^class BypassLaunchContext\b" src/` → 1 match.
  - Pyright enforces union exhaustiveness at executor dispatch via `match` +
    `assert_never`:
    - `rg "match\s+.*launch_context" src/meridian/lib/launch/process.py
      src/meridian/lib/launch/streaming_runner.py` → matches a `match`
      statement per executor.
    - `rg "assert_never\(" src/meridian/lib/launch/` → at least one per
      executor dispatch site.
    - `rg "pyright:\s*ignore" src/meridian/lib/launch/
      src/meridian/lib/ops/spawn/` → 0 matches. Enforced by the CI
      invariants script. (`pyright: ignore` is used elsewhere in-tree —
      e.g. `src/meridian/lib/harness/bundle.py:35`,
      `src/meridian/lib/app/server.py:342` — but banned in executor and
      spawn modules to prevent suppression of exhaustiveness checks.)
    - `rg "cast\(Any," src/meridian/lib/launch/
      src/meridian/lib/ops/spawn/` → 0 matches. `cast(Any, ctx)` evades
      match checking and must not appear in executor dispatch code.
  - `rg "^class RuntimeContext\b" src/` → exactly 1 match (unified).
  - Post-launch session-id extraction is **not** on `LaunchContext` — it is
    on `LaunchResult`, returned post-execution via adapter-owned
    `observe_session_id()`. `LaunchContext` is frozen and immutable. See
    §7 below.

  **Adapter boundary — no domain→concrete-harness imports:**
  - `rg "from meridian\.lib\.harness\.(claude|codex|opencode|projections)" src/meridian/lib/launch/`
    → 0 matches.
  - Domain core may import from `meridian.lib.harness.adapter` (abstract
    contract module) only. The current `claude_preflight` imports at
    `launch/process.py:29` and `launch/streaming_runner.py:28` move behind
    the adapter contract.

  **Driving-adapter invariant — exactly 3 factory callers (+1 preview):**
  - `rg "build_launch_context\(" src/ --type py` → exactly 4 call sites:
    - `launch/plan.py` or `launch/__init__.py` — primary launch (includes
      primary dry-run preview)
    - `ops/spawn/prepare.py` — background worker (includes spawn dry-run)
    - `app/server.py` — app streaming HTTP
    - One of the above serves dry-run preview; no additional file.
  - No other file calls the factory.

  **No composition outside core:**
  - `rg "TieredPermissionResolver\(" src/ --type py` → only inside the
    permission builder in `launch/permissions.py` (plus tests). Zero matches
    in `app/server.py`, `cli/streaming_serve.py`, or any driving adapter.
    **Heuristic limitations.** Evadable by aliasing (`from ...permissions
    import TieredPermissionResolver as TPR; TPR(...)`) or constructing an
    equivalent resolver under a different class name.
  - `rg "MERIDIAN_HARNESS_COMMAND" src/ --type py` → only inside
    `build_launch_context()` bypass branch in `launch/context.py` (plus
    tests). Zero matches in `launch/plan.py` or `launch/command.py`.
    **Heuristic limitations.** Evadable by string construction
    (`os.getenv("MERIDIAN_" + "HARNESS_COMMAND")`).
  - `rg "resolve_launch_spec\(" src/ --type py` → only inside
    `build_launch_context()` in `launch/context.py` and inside harness
    adapter implementations (`harness/claude.py`, `harness/codex.py`,
    `harness/opencode.py`). Zero matches in driving adapters, `app/server.py`,
    `spawn_manager.py`, or `streaming_runner.py`.
    **Heuristic limitations.** Evadable by method indirection
    (`r = adapter.resolve_launch_spec; r(params, perms)`).

  **Deletions completed:**
  - `rg "run_streaming_spawn" src/ --type py` → 0 matches (function and all
    imports/references deleted).
  - `rg "spec: ResolvedLaunchSpec \| None = None" src/meridian/lib/streaming/`
    → 0 matches (the optional-spec fallback in `SpawnManager.start_spawn` is
    removed; `spec` is required or replaced by `LaunchContext`).
  - `rg "UnsafeNoOpPermissionResolver" src/meridian/lib/streaming/` → 0
    matches (the fallback that used it is deleted).

  **Type split completed:**
  - `rg "^class SpawnRequest\b" src/` → 1 match (new user-facing DTO).
  - `rg "^class SpawnParams\b" src/` → 1 match (resolved execution inputs,
    possibly renamed). `SpawnParams` is not constructed outside the factory
    or `build_create_payload`.

- **Preserved divergences (not flattened by R06):**
  - Primary executor has two capture modes (PTY capture + direct Popen)
    driven by runtime environment. Both consume `LaunchContext`, return
    `LaunchResult`. The PTY path enables session-ID scraping; the Popen
    fallback loses session-ID observability today. GitHub issue #34 tracks
    moving to filesystem polling, which removes this asymmetry.
  - Claude-in-Claude sub-worktree cwd stays as a `child_cwd` field on
    `NormalLaunchContext`, populated by the pipeline.
  - `ensure_claude_session_accessible` import currently leaks from
    `harness/claude_preflight` into `launch/process.py:29` and
    `launch/streaming_runner.py:28`. R06 moves this behind the adapter
    contract so the domain core does not import concrete harness modules.

- **Fork continuation — absorbed into domain core (Option A, I/O-performing stage):**
  Fork materialization is pre-execution composition: both sites
  (`launch/process.py:68-105` and `ops/spawn/prepare.py:296-311`) call
  `adapter.fork_session()`, mutate `SpawnParams` via `model_copy`, and
  rebuild the command — all before any executor runs. The operation is
  identical in both drivers, gated by the same conditions (Codex adapter,
  has continuation session ID, not dry-run). R06 adds `materialize_fork()`
  as a pipeline stage in the domain core, running post-spec-resolution and
  pre-env-construction. This eliminates the duplication and prevents
  fork materialization from happening outside the factory.

  `materialize_fork()` performs state-mutating I/O: `fork_session()` opens
  SQLite (`~/.codex/state_5.sqlite`), reads thread rows, copies rollout files,
  and writes a new session id (`src/meridian/lib/harness/codex.py:425`).
  Several other stages read bounded configuration from disk during
  composition (profiles, skills, session state, `.claude/settings*.json`).
  `materialize_fork()` is distinguished as the only stage that **writes**.
  The factory's invariant is **centralization** — composition happens only
  in this pipeline — not purity.

  The session state dependency difference between the two sites is superficial:
  primary uses `plan.seed_harness_session_id`, worker uses
  `resolved_continue_harness_session_id` — both are "the resolved continuation
  session ID" available in the pipeline after spec resolution.

- **Test blast radius** (enumerate before refactoring):
  ```
  rg -l "RuntimeContext|prepare_launch_context|LaunchContext|build_launch_context\
  |build_launch_env|build_harness_child_env|PreparedSpawnPlan|resolve_policies\
  |resolve_permission_pipeline|SpawnParams|merge_env_overrides\
  |resolve_launch_spec|run_streaming_spawn|SpawnRequest|materialize_fork" tests/
  ```
  Known impacted test files include at minimum:
  - `tests/exec/test_streaming_runner.py`
  - `tests/exec/test_depth.py`
  - `tests/exec/test_permissions.py`
  - `tests/test_launch_process.py`
  - `tests/test_app_server.py`
  - `tests/ops/test_spawn_prepare_fork.py`
  - `tests/harness/test_codex_fork_session.py`

  Additional tests needed for new R06 deliverables:
  - `SpawnRequest` ↔ `SpawnParams` split boundary (construction, validation)
  - `materialize_fork()` pipeline stage (success, no-op when not Codex,
    empty session ID error)
  - Deletion verification (no test imports `run_streaming_spawn`)

  All identified tests must be updated in the same change set as the source
  refactor, not left as follow-up drift.

- **Suggested internal phasing:** R06 naturally decomposes into: (1)
  `SpawnRequest`/`SpawnParams` split (standalone DTO change); (2)
  `RuntimeContext` unification (standalone); (3) domain-core pipeline +
  `LaunchContext` sum type + `materialize_fork()` stage; (4) rewire primary
  launch to call factory; (5) rewire worker to call factory; (6) rewire
  app-streaming to call factory; (7) delete `run_streaming_spawn` + fold
  streaming serve CLI + remove `SpawnManager.start_spawn` fallback; (8)
  absorb `MERIDIAN_HARNESS_COMMAND` bypass into factory. Steps (1), (2), (3),
  and (7) can proceed independently; (4)–(6) land one driver at a time; (8)
  after (3). Each intermediate state satisfies a subset of the exit criteria.

  **6. CI enforcement script:**

  A CI step runs the `rg` suite above as a required status check. Without
  this, "CI-checkable via `rg`" is false — the current CI workflow
  (`.github/workflows/meridian-ci.yml:34-44`) runs only ruff/pyright/pytest/build.

  - `scripts/check-launch-invariants.sh` — shell script that executes each
    exit-criterion `rg` command, compares against expected results, and exits
    nonzero on drift.
  - `.github/workflows/meridian-ci.yml` — add a `check-launch-invariants`
    step that runs the script. Required status check.
  - Exit criterion: CI job `check-launch-invariants` passes on the R06
    branch before merge.

  **7. Session-ID adapter seam (`observe_session_id()`):**

  Session-ID observation moves off `LaunchContext` onto a post-execution
  `LaunchResult`. This closes the "all required, frozen" `LaunchContext`
  contradiction: session-ID is not a launch *input* — it is a post-launch
  *observable*.

  New types:

  ```python
  @dataclass(frozen=True)
  class LaunchOutcome:
      """Raw executor output before adapter post-processing."""
      exit_code: int
      child_pid: int | None
      captured_stdout: bytes | None  # PTY-captured output, if any

  @dataclass(frozen=True)
  class LaunchResult:
      """Post-processed launch result returned to driving adapters."""
      exit_code: int
      child_pid: int | None
      session_id: str | None  # populated by adapter.observe_session_id()
  ```

  New adapter method on the harness adapter protocol in
  `src/meridian/lib/harness/adapter.py`:

  ```python
  def observe_session_id(
      self,
      *,
      launch_context: NormalLaunchContext,
      launch_outcome: LaunchOutcome,
  ) -> str | None:
      """Return the session ID observed during this launch.

      Adapters observe session-ID via harness-native mechanisms during the
      normal course of launch. The method returns whatever the adapter
      observed; it is a getter over adapter-held state, not a parser of
      `launch_outcome`.
      """
  ```

  Executor contract:
  - Executor runs the process, returns a `LaunchOutcome` (raw: exit code,
    pid, any captured PTY output).
  - The driving adapter calls `harness_adapter.observe_session_id(...)`
    post-exec and assembles a `LaunchResult`.
  - `LaunchOutcome.captured_stdout` is populated only on the PTY capture
    path; streaming adapters observe session-ID via connection-bootstrap
    state they track internally, not from `captured_stdout`.
  - If observability fails (e.g., Popen fallback with today's scrape-only
    Claude impl), `session_id = None`. The surfacing layer already handles
    missing-session-id.

  Scope:
  1. Add `LaunchResult` and `LaunchOutcome` frozen dataclasses to
     `src/meridian/lib/launch/context.py` (or a new `launch/result.py`).
  2. Add `observe_session_id()` to the harness adapter protocol in
     `src/meridian/lib/harness/adapter.py`.
  3. Implement `observe_session_id()` in each harness adapter by
     **relocating existing session-ID code from executors** (Claude:
     scraper logic from `launch/process.py` or `streaming_runner.py`;
     Codex/OpenCode: stream-parse logic from streaming runner).
  4. Executors return `LaunchOutcome`; driving adapters call
     `observe_session_id()` and assemble `LaunchResult`.
  5. Remove `session_id` / `launch_session_id` fields from `LaunchContext`.
     `NormalLaunchContext` becomes genuinely all-required, frozen.
  6. Update executors' `match` + `assert_never` dispatch to the new types.

  Exit criteria:
  - `rg "^class LaunchResult\b" src/` → 1 match.
  - `rg "^class LaunchOutcome\b" src/` → 1 match.
  - `rg "observe_session_id\(" src/meridian/lib/harness/adapter.py` → 1
    match (protocol definition).
  - `rg "observe_session_id\(" src/meridian/lib/harness/ --type py` →
    matches in `adapter.py` (protocol) + `claude.py` + `codex.py` +
    `opencode.py` (implementations). Zero matches in `launch/` or
    `ops/spawn/`.
  - `rg "session_id" src/meridian/lib/launch/context.py` → 0 matches
    (session-ID is not a launch input).
  - **Heuristic limitations.** Same aliasing/indirection modes as other
    builder checks.

  Known limitation: R06 lands the adapter seam. Between R06 and the
  GitHub issue #34 mechanism swap to filesystem polling, the
  Popen-fallback-loses-session-ID bug persists for primary launch. The
  seam exists; implementations change later without touching executors.

  Existing observation mechanisms are preserved, not changed:
  - **Claude (PTY primary)**: scrapes terminal output during PTY capture;
    returns the scraped ID.
  - **Codex (streaming)**: reads `connection.session_id` set during WebSocket
    thread bootstrap (`src/meridian/lib/harness/connections/codex_ws.py:190,270`)
    and surfaced by `StreamingExtractor`
    (`src/meridian/lib/harness/extractor.py:43`).
  - **OpenCode (streaming)**: reads `connection.session_id` set during session
    creation
    (`src/meridian/lib/harness/connections/opencode_http.py:137,166`).

  The refactor **moves that logic behind the adapter method**. The
  mechanism swap to filesystem polling is GitHub issue #34.

- **Red flag (out of scope):** Background workers serialize `allowed_tools`
  but drop `disallowed_tools`, then re-resolve permissions without the
  denylist (`ops/spawn/execute.py:82-103`, `execute.py:861-865`,
  `prepare.py:323-328`). This is a correctness bug in the permission
  pipeline, not an R06 composition concern. Filed separately.
