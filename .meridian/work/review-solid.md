# SOLID / Extensibility Review

Scope: `src/meridian/lib/state/**`, `src/meridian/lib/launch/**`, relevant `core`, `harness`, `ops`, and CLI registration seams.

Method: static code review only. No tests run.

## Findings

### HIGH: `HarnessAdapter` is a kitchen-sink interface, and `DirectAdapter` is only nominally substitutable

References:
- `src/meridian/lib/harness/adapter.py:130`
- `src/meridian/lib/harness/direct.py:73`
- `src/meridian/lib/harness/registry.py:18`

Why it matters:
- `HarnessAdapter` mixes subprocess launch concerns, primary-session seeding, stream parsing, report extraction, session ownership detection, and optional summary/task extraction in one protocol.
- `DirectAdapter` has to implement subprocess-shaped methods it does not really support, including a fake `build_command()` that returns `["direct"]` and no-op parsing/session extraction methods.
- That is an interface-segregation failure and a Liskov warning sign: the three CLI-backed adapters are substitutable for the launcher, but `DirectAdapter` is only safe because callers happen to avoid the unsupported paths via capability flags.

Extensibility impact:
- Adding another non-subprocess harness or service-backed runtime will force more fake methods and more capability-driven branching.
- High-level launch code depends on one oversized protocol instead of the smaller contracts it actually needs.

Concrete fix:
- Split the contract into smaller protocols, for example:
  - `SubprocessHarnessAdapter`: `build_command()`, `env_overrides()`, `mcp_config()`, `blocked_child_env_vars()`
  - `StreamParsingHarness`: `parse_stream_event()`, `extract_usage()`, `extract_report()`, `extract_session_id()`
  - `PrimarySessionHarness`: `seed_session()`, `filter_launch_content()`, `detect_primary_session_id()`, `owns_untracked_session()`
  - `InProcessHarness`: `execute()`
- Make the registry expose typed adapters or an explicit runtime kind, so the launch pipeline only accepts `SubprocessHarnessAdapter` and direct mode only accepts `InProcessHarness`.

### HIGH: Session/work/materialization lifecycle policy is duplicated across primary launch and child spawn execution

References:
- `src/meridian/lib/launch/process.py:407`
- `src/meridian/lib/ops/spawn/execute.py:289`
- `src/meridian/lib/ops/spawn/execute.py:451`

Why it matters:
- `run_harness_process()` and `_session_execution_context()` both do session start/stop, active work auto-creation, harness-session updates, and materialized resource cleanup.
- The two flows are already close but not identical: primary launch also handles primary spawn bookkeeping and lock files, while child execution also resolves session agent materialization.
- This duplicates orchestration policy in two large modules, so changing session lifecycle rules means editing both places and re-validating subtle differences.

Extensibility impact:
- Adding a new session-level concern such as pinned artifacts, session metadata, reusable work bootstrap rules, or new cleanup stages will require parallel edits in both launch paths.
- The duplication raises the risk of primary and child runs drifting into different semantics.

Concrete fix:
- Extract a shared `SessionRunScope` service/context manager that owns:
  - session start/stop
  - active-work bootstrap
  - harness-session-id observation/update
  - harness materialization/cleanup
- Let primary launch and child spawn execution compose that shared scope with their own transport-specific concerns.

### MEDIUM: Primary launch resolution is performed twice through different APIs

References:
- `src/meridian/lib/launch/process.py:359`
- `src/meridian/lib/launch/resolve.py:184`
- `src/meridian/lib/launch/command.py:86`

Why it matters:
- `prepare_launch_context()` resolves `PrimarySessionMetadata`, then `run_harness_process()` calls `build_harness_context()`, which reloads the agent profile, re-resolves defaults, re-routes the harness, and re-resolves skills.
- That is a SRP/OCP problem: primary-launch policy is split between metadata resolution and command construction rather than expressed once as an immutable plan.

Extensibility impact:
- New launch policy fields will tend to require edits in both resolution paths.
- Divergence bugs are likely if one path learns a new rule and the other does not.

Suggested approach:
- Replace the current split with one `ResolvedPrimaryLaunchPlan` that contains metadata, resolved adapter, materialization result, permission config, and final `SpawnParams`.
- Let `process.py` consume that plan instead of recomputing any policy.

### MEDIUM: Spawn execution crosses too many boundaries through shape-based inputs instead of cohesive value objects

References:
- `src/meridian/lib/ops/spawn/execute.py:70`
- `src/meridian/lib/ops/spawn/execute.py:364`
- `src/meridian/lib/launch/runner.py:484`

Why it matters:
- `_PreparedCreateLike` is a 17+ property protocol, which is effectively a hidden DTO without a concrete type.
- `execute_with_finalization()` also takes a very broad argument list, mixing execution policy, retry policy, environment, streaming, security, budget, and session concerns.

Extensibility impact:
- Adding one execution concern often means threading data through multiple function signatures, background-worker argv serialization, and protocol properties.
- This is a common source of “touch 10 files to add one field” churn.

Suggested approach:
- Introduce a concrete immutable `PreparedSpawnPlan` plus smaller nested objects such as `ExecutionPolicy`, `RetryPolicy`, and `SessionContinuation`.
- Use that same plan for blocking, background, and resumed execution.

### MEDIUM: The spawn lifecycle is only partially centralized; state-machine rules are still fragmented

References:
- `src/meridian/lib/core/spawn_lifecycle.py:1`
- `src/meridian/lib/state/spawn_store.py:68`
- `src/meridian/lib/launch/runner.py:484`
- `src/meridian/lib/state/reaper.py:164`

Why it matters:
- `spawn_lifecycle.py` centralizes terminal-state normalization, which is good, but the rest of the lifecycle still lives in raw string checks spread across the store, runner, primary process path, and reaper.
- `queued` vs `running` recovery, launch-mode inference, retry behavior, and reconciliation outcomes are encoded in several places instead of in a single transition model.

Extensibility impact:
- New states such as `cancelled`, `retrying`, or `paused` would require coordinated edits across multiple modules.
- The design already leans toward a state machine, but the implementation has not completed that abstraction.

Suggested approach:
- Define explicit lifecycle events and allowed transitions in one domain module, and have store/runner/reaper call transition helpers instead of encoding status strings directly.

### MEDIUM: CLI registration is only partially open for extension

References:
- `src/meridian/lib/ops/manifest.py:216`
- `src/meridian/cli/main.py:627`
- `src/meridian/cli/spawn.py:390`

Why it matters:
- Operations are centralized in the manifest, which is good, but CLI registration is still manual by group.
- Adding a new CLI command group currently requires at least a manifest entry, a group module with a hand-built handler map, and an explicit registration call in `cli/main.py`.

Extensibility impact:
- The system is not yet at the stated “new CLI command = one module” ideal.
- The repeated `register_*_commands()` pattern also duplicates manifest-to-handler wiring logic across modules.

Suggested approach:
- Move group registration to a declarative registry derived from the manifest, or let each CLI module self-register via a discovered plugin list rather than hard-coding imports in `main.py`.

### LOW: State stores duplicate generic event-log mechanics and bundle several responsibilities per file

References:
- `src/meridian/lib/state/spawn_store.py:27`
- `src/meridian/lib/state/session_store.py:83`

Why it matters:
- `spawn_store.py` and `session_store.py` each implement their own locking, JSONL append, parsing, and projection loops.
- `session_store.py` also combines event persistence, lock-handle ownership, projection, active-session queries, and stale-session cleanup.

Extensibility impact:
- Adding a new state entity will likely involve copying one of these stores and editing it by hand.

Note:
- This is not urgent if the number of state entities stays small, but it is a real extensibility tax.

## Pattern Notes

- Harness adapters are a reasonable strategy pattern for CLI-backed runtimes. `claude`, `codex`, and `opencode` look broadly consistent on the subprocess contract.
- The file-backed state model and atomic writes align well with the crash-only design goals.
- The main missing pattern is a first-class state machine for spawn lifecycle and a narrower adapter hierarchy for runtime kinds.

## Verification

- Review artifact written.
- No automated tests run.
