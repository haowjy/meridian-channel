# Launch Domain Core Architecture

## Summary

The launch subsystem is a typed pipeline owned by one factory. Three driving
adapters (primary launch, background worker, app streaming HTTP) each construct
a raw `SpawnRequest`, hand it to `build_launch_context()`, and receive a
complete `LaunchContext` for execution. Two executors (primary
foreground capture-mode branch and async subprocess) consume `LaunchContext`,
emit `LaunchOutcome`, and the driving adapter then asks the selected driven
adapter to observe the session id and assemble `LaunchResult`. Composition
lives only inside the factory's pipeline stages; drivers carry user-facing
intent and durable state-machine concerns, never composition logic.

This leaf is observational. It describes the target shape and the constraints
that implementation and review must preserve. The agenda for getting from the
current state to this shape is `../refactors.md`.

## Structural Role

This architecture provides the single-composition-seam invariant that enables:

- **Future workspace projection:** A single `build_launch_context()` factory with fixed pipeline ordering gives exactly one insertion point for any `apply_workspace_projection()` stage.
- **Context-root injection:** Harness integration for context-root injection plugs into the seam this architecture provides.
- **Dry-run / runtime parity:** A single bypass branch (`_build_bypass_context()`) ensures dry-run preview and runtime execute the same preflight expansion.

## Current State

- `build_launch_context()` exists at
  `src/meridian/lib/launch/context.py:31-213`, but accepts a pre-resolved
  `PreparedSpawnPlan` whose `ExecutionPolicy` already carries
  `PermissionConfig` + live `PermissionResolver`
  (`src/meridian/lib/ops/spawn/plan.py:9-65`).
- Composition is therefore performed in every driving adapter before the
  factory call: `launch/plan.py:234-410`, `ops/spawn/prepare.py:202-397`,
  `app/server.py:286-351`, `cli/streaming_serve.py:65-87`,
  `ops/spawn/execute.py:397-425`.
- `SpawnRequest` exists on the harness adapter protocol at
  `src/meridian/lib/harness/adapter.py:150-163`, currently unused. Dead
  abstraction signal.
- `LaunchContext = NormalLaunchContext | BypassLaunchContext` is a sum type
  but app-server dispatch uses an `isinstance` branch, not exhaustive `match`
  (`src/meridian/lib/app/server.py:364`).
- Bypass logic is duplicated between `launch/__init__.py:65-77` (dry-run
  preview) and `launch/context.py:153-173` (runtime).
- Stage modules are placeholders: `launch/policies.py`, `launch/permissions.py`,
  `launch/runner.py` are re-export shells or empty files. Real composition
  happens elsewhere.
- Fork materialization has two callers: `launch/fork.py:7-34` (factory path)
  and inline `ops/spawn/prepare.py:296-311` (worker prepare path, before any
  spawn row exists — correctness review D4).
- `observe_session_id()` is declared on the protocol
  (`src/meridian/lib/harness/adapter.py:332,466`) but no concrete adapter
  implements it; observation still flows through
  `launch/session_ids.py:16-54` plus inline scrape paths in
  `launch/process.py:451-476` and `launch/streaming_runner.py:859-883`.
- `harness/adapter.py:41-121` projects concrete permission flags inside the
  port contract module — mechanism leaked into supposed abstraction root.
- Verification today is `scripts/check-launch-invariants.sh`, an
  `rg`-count-based gate that the structural review enumerated 14 evasion
  patterns for.

The shape is half-built: the domain core's package silhouette landed, but the
core itself did not.

## Target State

### Boundary diagram

```
   Primary launch ─┐
                    │
   Worker         ─┼──▶ build_launch_context(SpawnRequest, LaunchRuntime, *, dry_run)
                    │             │
   App streaming  ─┘             │  pipeline (single owner each):
                                  │  ├── (bypass branch — sole owner)
   Dry-run preview ───────────────┤  ├── resolve_policies()
                                  │  ├── resolve_permission_pipeline()
                                  │  ├── compose_prompt()
                                  │  ├── build_resolved_run_inputs()
                                  │  ├── materialize_fork()                ← gated by dry_run
                                  │  ├── resolve_launch_spec_stage()
                                  │  ├── apply_workspace_projection()      ← future seam
                                  │  ├── build_launch_argv()
                                  │  └── build_env_plan()
                                  ▼
                            LaunchContext
                          (Normal | Bypass, with warnings)
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

### Type ladder

Four user-visible types, two factory-internal types. Every type below is
frozen (pydantic `model_config = {"frozen": True}` or
`@dataclass(frozen=True)`); none use `arbitrary_types_allowed`.

- **`SpawnRequest`** (user-visible). Frozen pydantic model. Fully
  serializable: `model_dump_json` / `model_validate_json` round-trip without
  `arbitrary_types_allowed`. Carries only what an external caller can
  express. Fields:
  - **Prompt / agent / skills:** `prompt: str`, `model: str`,
    `harness: str | None`, `agent: str | None`, `skills: tuple[str, ...]`.
  - **Harness shape:** `extra_args: tuple[str, ...]`,
    `mcp_tools: tuple[str, ...]`, `sandbox: str | None`,
    `approval: str | None`, `allowed_tools: tuple[str, ...]`,
    `disallowed_tools: tuple[str, ...]`, `autocompact: bool | None`,
    `effort: str | None`.
  - **Execution policy:** `retry: RetryPolicy` (nested frozen model:
    `max_attempts: int`, `backoff_secs: float`),
    `budget: ExecutionBudget` (nested frozen model: `timeout_secs: int |
    None`, `kill_grace_secs: int | None`).
  - **Session intent:** `session: SessionRequest` (nested frozen model
    carrying all eight prior `SessionContinuation` fields:
    `continue_chat_id: str | None`, `requested_harness_session_id:
    str | None`, `continue_fork: bool`, `source_execution_cwd:
    str | None`, `forked_from_chat_id: str | None`,
    `continue_harness: str | None`, `continue_source_tracked: bool`,
    `continue_source_ref: str | None`).
  - **Context plumbing:** `context_from: str | None` (raw chat-id ref;
    factory resolves to materialized files), `reference_files:
    tuple[str, ...]`, `template_vars: dict[str, str]`.
  - **Routing & metadata:** `work_id_hint: str | None`,
    `agent_metadata: dict[str, str]`.

  All `Path`-shaped fields are stored as `str` so `model_dump_json` round-trips
  without custom encoders. **Constructed by every driving adapter and only
  by them.**

- **`LaunchRuntime`** (user-visible). Frozen pydantic model. Carries
  runtime-injected (non-user-input) context the driving adapter knows but
  the caller does not provide:
  - `launch_mode: Literal["primary", "background"]` — discriminates
    foreground primary launch from background/app-streaming. Drives
    `interactive` projection on each driven adapter.
  - `unsafe_no_permissions: bool` — selects
    `UnsafeNoOpPermissionResolver` inside `resolve_permission_pipeline()`.
  - `debug: bool` — propagates the worker `--debug` flag to env.
  - `harness_command_override: str | None` — surfaces
    `MERIDIAN_HARNESS_COMMAND` value seen by the driving adapter (factory
    parses; the driver does not).
  - `report_output_path: str | None` — file path the executor will write
    the final report to.
  - `state_paths: StatePaths`, `project_paths: ProjectPaths` — already-resolved
    path roots.

  **Constructed by every driving adapter and only by them.** `SpawnRequest`
  + `LaunchRuntime` together form the complete factory input surface.

- **`LaunchContext = NormalLaunchContext | BypassLaunchContext`**
  (user-visible sum). Frozen, all-required. Executor input.
  - `NormalLaunchContext`: `argv`, `env`, `child_cwd`, `spec`
    (`ResolvedLaunchSpec`), `run_inputs: ResolvedRunInputs` (readable but
    not driver-reconstructable), `perms` (live `PermissionResolver`),
    `report_output_path`, `harness_adapter` ref,
    `warnings: tuple[CompositionWarning, ...]`.
  - `BypassLaunchContext`: `argv`, `env`, `child_cwd`,
    `warnings: tuple[CompositionWarning, ...]`. No spec, no perms —
    bypass is opaque to harness composition.

- **`LaunchResult`** (user-visible). `exit_code`, `child_pid`, `session_id`.
  `session_id` is populated by `harness.observe_session_id()` after the
  executor returns. Driving adapters consume `LaunchResult`.

- **`CompositionWarning`** (user-visible auxiliary). Frozen pydantic model:
  `code: str`, `message: str`, `detail: dict[str, str] | None`. Pipeline
  stages append warnings to the `LaunchContext` they return; drivers
  surface them through `SpawnActionOutput.warning`. Replaces the deleted
  `PreparedSpawnPlan.warning` channel.

- **`ResolvedRunInputs`** (factory-internal — renamed from today's
  `SpawnParams`). Constructed only inside `build_launch_context()` by
  `build_resolved_run_inputs()`. Carries skills-resolved-to-paths,
  continuation ids, appended prompts, materialized `context_from` payload,
  report paths, prompt composition outputs. Driving adapters never
  construct or directly consume this type.

- **`LaunchOutcome`** (factory-internal — executor-to-driving-adapter
  handoff). Raw `exit_code`, `child_pid`, optional `captured_stdout`
  (PTY-captured bytes/str when the primary executor's PTY mode is active;
  empty otherwise). The driving adapter MUST NOT inspect
  `captured_stdout` directly to scrape session ids — that observation is
  the driven adapter's job via `observe_session_id()`.

Deleted from the prior shape: `PreparedSpawnPlan`, `ExecutionPolicy`,
top-level `SessionContinuation`, `ResolvedPrimaryLaunchPlan`, the
user-facing form of `SpawnParams`. Type count drops from 6 partial-truth
DTOs to 7 named types with one-sentence purposes (4 user-visible
DTOs + `CompositionWarning` auxiliary + 2 factory-internal types).

### Pipeline stages (one owner each, no re-export shells)

| Stage | Owning module | Function | Inputs | Outputs |
|---|---|---|---|---|
| Bypass dispatch | `launch/context.py` | `_build_bypass_context()` | `SpawnRequest`, `LaunchRuntime` | `BypassLaunchContext` (sole `MERIDIAN_HARNESS_COMMAND` parser) |
| Policy resolution | `launch/policies.py` | `resolve_policies` | `SpawnRequest`, `ProjectPaths` | `ResolvedPolicies` |
| Permission resolution | `launch/permissions.py` | `resolve_permission_pipeline` | sandbox, allowed_tools, disallowed_tools, approval, `runtime.unsafe_no_permissions` | `(PermissionConfig, PermissionResolver)` — sole `TieredPermissionResolver` / `UnsafeNoOpPermissionResolver` constructor |
| Prompt composition | `launch/prompt.py` | `compose_prompt` | `SpawnRequest`, policies, harness | `ComposedPrompt` (sole `adapter.seed_session` + `adapter.filter_launch_content` callsite) |
| Run-input aggregation | `launch/run_inputs.py` (new) | `build_resolved_run_inputs` | policies, permissions, prompt, materialized `context_from` payload | `ResolvedRunInputs` |
| Fork materialization | `launch/fork.py` | `materialize_fork(*, adapter, run_inputs, dry_run, spawn_id)` | adapter, run_inputs, dry_run, existing spawn_id | `ResolvedRunInputs` (with new session id when forked) — sole `adapter.fork_session` callsite; precondition: spawn row exists |
| Spec resolution | `launch/command.py` | `resolve_launch_spec_stage` | adapter, run_inputs, perms | `ResolvedLaunchSpec` — sole `adapter.resolve_launch_spec` callsite |
| Workspace projection (future seam) | `launch/command.py` | `apply_workspace_projection` | adapter, spec, runtime | `ResolvedLaunchSpec` (with `extra_args` extended by `projection.extra_args`) — sole `adapter.project_workspace` callsite |
| Argv build | `launch/command.py` | `build_launch_argv` | adapter, projected spec | `tuple[str, ...]` — sole `adapter.build_command` callsite |
| Env plan | `launch/env.py` | `build_env_plan` | adapter, run_inputs, permission_config, `runtime` overrides, base env | `Mapping[str, str]` — sole env builder; sole `build_harness_child_env` caller |

The factory composes these in fixed order. Each function has exactly one
caller (the factory). Each stage has one owned file; no re-export shells
remain.

### Factory invariant

The factory's invariant is **centralization**, not purity. Several stages
read bounded configuration from disk (profiles, skills, session state,
`.claude/settings*.json`); `materialize_fork()` is the sole stage that
performs state-mutating I/O against external Codex SQLite. The architectural
property the type system and tests must enforce is:

> Every composition step is performed inside `build_launch_context()` and
> the named pipeline stages it calls. Driving adapters carry user-facing
> intent and durable state-machine concerns only.

### Driving adapters

Three adapters. Same names as today; new responsibility. Each constructs
both `SpawnRequest` (caller-expressible inputs) and `LaunchRuntime`
(runtime-injected context the caller does not provide), hands them to
the factory, dispatches the resulting `LaunchContext` to the right
executor, and assembles `LaunchResult`.

- **Primary launch** — `launch/plan.py` → `launch/process.py`. Foreground
  process under meridian's control until exit. Constructs
  `LaunchRuntime(launch_mode="primary", ...)`. Two capture modes (PTY
  capture + direct Popen) live on the executor side; both consume
  `LaunchContext` and return `LaunchOutcome`. PTY enables session-ID
  observation through `observe_session_id()`. Popen loses session-ID
  observability today (GitHub issue #34 tracks filesystem-polling fix).
  The driving adapter is the sole owner of: spawn-row creation, calling
  the factory, dispatching the executor, invoking `observe_session_id()`,
  finalizing the spawn row, surfacing
  `LaunchContext.warnings` to `SpawnActionOutput.warning`.

- **Background worker** — `ops/spawn/prepare.py` → `ops/spawn/execute.py`.
  `prepare.py` constructs and persists `SpawnRequest`; the persisted
  artifact replaces today's `PreparedSpawnPlan`. `execute.py` reads the
  persisted `SpawnRequest`, constructs a fresh `LaunchRuntime(launch_mode=
  "background", debug=..., ...)`, creates the spawn row, then calls
  `build_launch_context(..., dry_run=False)`. Fork happens inside the
  factory call, after the row exists. The worker explicitly re-resolves
  composition on execute (re-reads filesystem state at execute time);
  there is no persisted `cli_command` preview cached from prepare. This
  is a behavior-preserving simplification — today's worker also reconstructs
  the resolver at execute time.

- **App streaming HTTP** — `app/server.py`. In-process `SpawnManager`
  control channel. Constructs `SpawnRequest` and
  `LaunchRuntime(launch_mode="background", unsafe_no_permissions=
  cli_flag, ...)`, creates the spawn row, calls the factory.
  `TieredPermissionResolver` and `UnsafeNoOpPermissionResolver` are no
  longer constructed here — the unsafe override flows through
  `runtime.unsafe_no_permissions` and dispatches inside
  `resolve_permission_pipeline()`. Sum-type dispatch uses exhaustive
  `match` over `LaunchContext` with `assert_never` default.

`cli/streaming_serve.py` driver is removed entirely — its
responsibilities collapse into the app streaming driver because both
already construct identical pre-composed plans against the same
factory boundary.

Dry-run callers (preview/`--dry-run`) call the factory with `dry_run=True`
and consume the `LaunchContext` for printing; they do not invoke an
executor. Bypass dry-run produces the same argv as bypass runtime because
preflight runs inside the bypass branch.

### Executors

Two executors. Each accepts `LaunchContext`, dispatches via `match` +
`assert_never` on the sum type, returns `LaunchOutcome`.

- **Primary foreground** (`launch/process.py`) — primary launch only.
  Capture-mode branch (PTY/Popen) is internal.
- **Async subprocess** (`launch/streaming_runner.py`) — worker + app
  streaming share. Single precondition: the spawn row must exist before
  `execute_with_streaming` is called. The fallback inside
  `execute_with_streaming` no longer creates rows on demand; callers that
  could reach this path with no row become a fail-fast error.

Executors do not know about session ids, harness identities, or composition
inputs. They consume `LaunchContext`, run a process, return `LaunchOutcome`.

### Driven adapters

`harness/claude.py`, `harness/codex.py`, `harness/opencode.py`. The port
contract module (`harness/adapter.py`) declares contracts only —
Protocols, abstract base classes, and frozen DTOs:
`HarnessCapabilities`, `RunPromptPolicy`, `SpawnRequest`, `LaunchRuntime`,
`SessionRequest`, `RetryPolicy`, `ExecutionBudget`, `HarnessAdapter`,
`SubprocessHarness`, `observe_session_id` slot, `project_workspace` slot,
`seed_session` slot, `filter_launch_content` slot.

The port MUST NOT contain concrete permission-flag projection logic,
concrete env construction, concrete session-ID observation, or concrete
command-argv assembly. All such mechanism moves into each adapter's
own file (`env_overrides()`, `build_command()`, `observe_session_id()`,
`project_workspace()`) as appropriate. The port stops carrying mechanism.

### Session-ID adapter seam

Per-adapter `observe_session_id(*, launch_context, launch_outcome) -> str
| None`. The contract permits two legitimate observation sources, both
strictly per-launch:

1. **Parsed from `launch_outcome.captured_stdout`** when the executor's
   PTY mode actually populated it (Claude primary launch). The adapter
   parses output it received as the function input — this is observation
   of per-launch state, not adapter-instance state.
2. **Read from per-launch state reachable via `launch_context`** —
   primarily the connection object held inside `NormalLaunchContext` for
   HTTP/WS-driven harnesses (codex / opencode `connection.session_id`).

What the contract forbids is any field on the adapter class instance that
holds a session id, chat id, or last-launch state shared across launches.
`observe_session_id` is purely a function of its per-launch inputs; no
`_observed_session_id`-style mutable singleton on the adapter.

Per-adapter realization:

- **Claude** (`harness/claude.py`) — parse from
  `launch_outcome.captured_stdout` for primary PTY mode. Popen mode has
  no source today; returns `None`. GitHub issue #34 tracks the
  filesystem-polling fix that removes the Popen degradation without
  touching this seam.
- **Codex** (`harness/codex.py`) — read `connection.session_id` set during
  WebSocket thread bootstrap (`harness/connections/codex_ws.py:190,270`),
  reached through `launch_context`.
- **OpenCode** (`harness/opencode.py`) — read `connection.session_id` set
  during session creation (`harness/connections/opencode_http.py:137,166`),
  reached through `launch_context`.

The driving adapter calls `harness.observe_session_id(...)` exactly once
after the executor returns, then assembles `LaunchResult`. The spawn-row
update for `harness_session_id` happens with this value.
`launch/session_ids.py` is deleted; inline scrape paths in
`launch/process.py` and `launch/streaming_runner.py` are deleted.

### Fork transaction ordering

Fork materialization is a side effect against external Codex SQLite.
Fork-after-row is enforced in every driver:

| Driver | Fork happens | Row exists when fork happens? |
|---|---|---|
| Worker prepare phase | (does not fork — only persists `SpawnRequest`) | n/a |
| Worker execute phase | inside factory call | yes — row created before factory |
| Primary launch | inside factory call | yes — row created at `process.py:306` before factory at `process.py:328` (already correct, locked by behavioral test) |
| App streaming | inside factory call | yes — row created before factory |
| Streaming-runner fallback | inside factory call | yes — fallback creates row before calling factory; missing-row case becomes fail-fast precondition error |

Failure semantics: if `materialize_fork` raises after the spawn row exists,
the driving adapter marks the spawn row `failed` with reason
`fork_materialization_error` and re-raises. Codex rollouts are append-only
with content-addressed naming; orphan rollouts on the codex side are
tolerated. The orphan-fork window collapses to "spawn row marked failed
with identifiable reason" — recoverable via the documented reason code.

Child cwd creation (`resolve_child_execution_cwd` + `mkdir`) happens
inside the factory after the row exists. The `launch/cwd.py` helper
signature changes so callers cannot create the cwd without supplying the
spawn id of an existing row.

### Bypass branch

`MERIDIAN_HARNESS_COMMAND` parsing has one owner: `_build_bypass_context()`
inside `launch/context.py`. The factory branches on bypass first; both
dry-run and runtime walk the same branch, so dry-run argv equals runtime
argv. Preflight runs inside the bypass branch (Claude's preflight expansion
includes `--add-dir` injection), so nested-Claude bypass dry-run preview
matches what runtime will execute.

The duplicate parse in `launch/__init__.py:65-77` and the legacy parse in
`launch/command.py:53` are deleted. The factory is the only place that
reads `MERIDIAN_HARNESS_COMMAND`.

### Persisted artifact

`prepare.py` persists a `SpawnRequest` JSON blob, not a `PreparedSpawnPlan`.
The persisted artifact contains no live objects (no resolver, no resolved
config), so `arbitrary_types_allowed=True` is no longer needed on any
launch DTO. `Path`-shaped fields on `SpawnRequest` (and every nested model
that participates in the round-trip) are stored as `str` so
`model_dump_json` / `model_validate_json` round-trip without custom
encoders. `execute.py` reconstructs the resolver from the raw inputs by
constructing a fresh `LaunchRuntime` and calling the factory exactly the
same way every other driver does.

This is a strict simplification: the resolver was already reconstructed
at execute time today (`execute.py:861`), so the persisted live object
was never load-bearing across the boundary.

`spawn show --plan` operates against the persisted `SpawnRequest` rather
than a pre-composed plan. Operators inspecting the artifact see the
caller's input intent, not a snapshot of resolved composition state — the
latter is recomputed deterministically on `execute`.

## Cross-Cutting Constraints

These constraints are what the type system, behavioral tests, and the
CI architectural drift gate must enforce together.

### Single-owner table

| Concern | Sole owner |
|---|---|
| Bypass dispatch | `launch/context.py:_build_bypass_context()` |
| `MERIDIAN_HARNESS_COMMAND` resolution | `launch/context.py:_build_bypass_context()` |
| Adapter `resolve_launch_spec` callsite | `launch/command.py:resolve_launch_spec_stage()` |
| Adapter `project_workspace` callsite | `launch/command.py:apply_workspace_projection()` |
| Adapter `build_command` callsite | `launch/command.py:build_launch_argv()` |
| Adapter `fork_session` callsite | `launch/fork.py:materialize_fork()` |
| Adapter `seed_session` / `filter_launch_content` callsite | `launch/prompt.py:compose_prompt()` |
| Fork materialization | `launch/fork.py:materialize_fork()` |
| `TieredPermissionResolver` construction | `launch/permissions.py:resolve_permission_pipeline()` |
| `UnsafeNoOpPermissionResolver` construction | `launch/permissions.py:resolve_permission_pipeline()` |
| Session-ID observation | per-adapter `observe_session_id()` (claude/codex/opencode); driving adapter calls once post-execution |
| `RuntimeContext` type | one type in `core/context.py` (`launch/context.py:42` duplicate deleted) |
| Child cwd creation (`mkdir`) | inside the factory after spawn row exists |
| `SpawnRequest` construction | every driving adapter and only them |
| `LaunchRuntime` construction | every driving adapter and only them |
| `ResolvedRunInputs` construction | inside `build_launch_context()` only |
| Composition warnings sidechannel | `LaunchContext.warnings` (no other path) |

### Driving-adapter prohibition list

Driving adapters (`launch/plan.py`, `launch/process.py`,
`ops/spawn/prepare.py`, `ops/spawn/execute.py`, `app/server.py`,
`cli/streaming_serve.py`) MUST NOT directly call (or rename / dynamic-import):

- `resolve_policies`
- `resolve_permission_pipeline`
- `TieredPermissionResolver(...)`
- `UnsafeNoOpPermissionResolver(...)`
- `adapter.resolve_launch_spec`
- `adapter.project_workspace`
- `adapter.build_command`
- `adapter.fork_session`
- `adapter.seed_session`
- `adapter.filter_launch_content`
- `build_harness_child_env`
- `extract_latest_session_id` (function deleted)

Driving adapters MUST NOT directly construct `PermissionConfig`,
`ResolvedLaunchSpec`, or `ResolvedRunInputs`. Driving adapters MUST NOT
inspect `LaunchOutcome.captured_stdout` directly to scrape session ids —
session-ID observation is exclusively the driven adapter's responsibility
via `observe_session_id()`.

If a driver needs any of these, it constructs `SpawnRequest` +
`LaunchRuntime` and calls `build_launch_context()`.

### Shape constraints

- `LaunchContext` sum-type dispatch uses exhaustive `match` + `assert_never`,
  not `isinstance` chains. New variants force a type error at every dispatch
  site.
- `NormalLaunchContext` and `BypassLaunchContext` are frozen with no
  optional load-bearing fields. A constructed context is complete; no
  field with `None` default is load-bearing for executor behavior.
- `SpawnRequest`, `LaunchRuntime`, `ResolvedRunInputs`, `LaunchOutcome`,
  `LaunchResult`, `CompositionWarning`, and every nested model
  (`SessionRequest`, `RetryPolicy`, `ExecutionBudget`) are frozen pydantic
  models or `@dataclass(frozen=True)` types with JSON-primitive fields
  only. `arbitrary_types_allowed` is forbidden on every model in
  `launch/`, `harness/`, `ops/spawn/`, and `app/`.
- All `Path`-shaped fields on `SpawnRequest` and nested models are stored
  as `str` to preserve `model_dump_json` round-trip without custom
  encoders.
- `harness/adapter.py` declares contracts only. No concrete permission-flag
  projection, no concrete env composition, no concrete observation logic,
  no concrete command-argv assembly.
- Stage modules (`launch/policies.py`, `launch/permissions.py`,
  `launch/fork.py`, `launch/env.py`, `launch/command.py`,
  `launch/run_inputs.py`, `launch/prompt.py`) own real definitions. None
  are re-export shells.
- Composition warnings have one sidechannel: `LaunchContext.warnings`.
  No other path is permitted.

## Verification

`scripts/check-launch-invariants.sh` is deleted. The
`check-launch-invariants` step is removed from
`.github/workflows/meridian-ci.yml`. Verification is three layers:

**1. Behavioral factory tests.** `tests/launch/test_launch_factory.py`
pins load-bearing invariants directly. Required tests are enumerated in
`../refactors.md` verification section.

**2. CI architectural drift gate.** A `meridian spawn -a reviewer` step
runs only on PRs that touch `src/meridian/lib/(launch|harness|ops/spawn|app)/`
or `src/meridian/cli/streaming_serve.py`. The reviewer reads the diff
against `.meridian/invariants/launch-composition-invariant.md`
(a version-controlled declared-intent prose file). It returns `pass | fail`
with file:line violations and CI blocks merge on `fail`.

**3. pyright + ruff + pytest** remain the correctness gate. The drift gate
sits beside them, not in place of them.

## Resolved Behaviors

- **Workspace projection insertion point reachable.** Workspace projection is its
  own pipeline stage — `apply_workspace_projection()` — sitting between
  `resolve_launch_spec_stage()` and `build_launch_argv()`.
- **Dry-run / runtime parity.** Bypass dry-run argv equals bypass runtime
  argv because both walk `_build_bypass_context()` with the same preflight
  call.
- **Persisted-artifact serializability.** The worker `prepare → execute`
  artifact is plain JSON — no `arbitrary_types_allowed`, no live objects.
- **Background worker `disallowed_tools` correctness.** The current bug
  where workers serialize `allowed_tools` but drop `disallowed_tools`
  becomes structurally fixable as soon as the worker persists `SpawnRequest`,
  because `SpawnRequest.disallowed_tools` is a first-class field.
- **Popen-fallback session-ID observability.** Preserved as a known
  limitation under issue #34. This refactor lands the `observe_session_id()` seam;
  the mechanism swap to filesystem polling is a separate change.

## What This Leaf Does Not Cover

- Per-harness workspace projection mechanics.
- Workspace topology model and validation.
- Project-root file boundary (`ProjectPaths` vs `StatePaths`).
- Config loader state machine.
- `config show`, `doctor`, and launch-diagnostic shapes.
- Removing dead legacy subprocess-runner code and clarifying misleading
  `_subprocess` filenames — issue #32.
