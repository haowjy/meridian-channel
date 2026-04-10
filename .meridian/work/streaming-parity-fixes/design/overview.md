# Streaming Parity — Design Overview (v2)

## Entry Point

This directory describes the **target shape** for launch-spec-based parity between the subprocess and streaming code paths. It is a re-shape, not a patch set. The v1 refactor (archived at `.meridian/work-archive/streaming-adapter-parity/`) introduced the transport-neutral `ResolvedLaunchSpec` but stopped short of committing to it — leaving silent fallbacks, half-typed dispatch, and a missing projection-side guard that together caused the four HIGH findings in the post-impl review (p1411).

Read the docs in this order on first pass:

| # | Doc | What it covers |
|---|-----|---------------|
| 1 | [overview.md](overview.md) | This file — problem framing, architectural shape, enumerated failure modes |
| 2 | [typed-harness.md](typed-harness.md) | `HarnessAdapter[SpecT]` + `HarnessConnection[SpecT]` — the generic type contract that eliminates isinstance branching |
| 3 | [launch-spec.md](launch-spec.md) | Spec hierarchy, field ownership rules, factory contract, no base fallbacks |
| 4 | [transport-projections.md](transport-projections.md) | Shared projection functions, canonical arg ordering, completeness guards |
| 5 | [permission-pipeline.md](permission-pipeline.md) | `PermissionResolver` is non-optional end-to-end; `config` becomes a Protocol property |
| 6 | [runner-shared-core.md](runner-shared-core.md) | `LaunchContext` — shared preflight/env/constants so runners cannot drift |
| 7 | [edge-cases.md](edge-cases.md) | Every enumerated failure mode. Every edge case here has a scenario file in `scenarios/` |

## Problem

Two code paths translate `SpawnParams` into harness-native configuration:

- **Subprocess path**: `runner.py` → `adapter.build_command()` → CLI args for `claude`, `codex exec`, `opencode run`.
- **Streaming path**: `streaming_runner.py` / `server.py` / `run_streaming_spawn` → `adapter.resolve_launch_spec()` → connection adapter (`claude_ws.py`, `codex_ws.py`, `opencode_http.py`) → CLI args / JSON-RPC / HTTP payload for `claude -p --input-format stream-json`, `codex app-server`, `opencode serve`.

The v1 refactor introduced `ResolvedLaunchSpec` as the shared contract. It intended the spec to be the single policy layer — but the implementation still allowed silent bypasses of that contract at every boundary where the type system wasn't enforcing it:

- **Base-class fallback** (`BaseSubprocessHarness.resolve_launch_spec` returns a generic `ResolvedLaunchSpec`) defeats the per-harness factory pattern. Any adapter that forgets to override it silently drops every harness-specific field.
- **Isinstance branching in every connection adapter** (`if isinstance(spec, ClaudeLaunchSpec): ...`) combined with `spawn_manager.py:99`'s `spec or ResolvedLaunchSpec(prompt=config.prompt)` fallback means a caller that omits the spec silently gets base-class behavior and all harness-specific fields vanish.
- **Two `cast("PermissionResolver", None)` at `streaming_runner.py:457` and `server.py:203`** lie to the type system. `resolve_permission_config(None)` quietly returns a default via `getattr` fallback, so Claude streaming emits zero permission flags, Codex collapses to accept-all, and OpenCode env overrides become empty — through the main async entry point and the entire REST server.
- **`CodexLaunchSpec.sandbox_mode` and `.approval_mode` are stored but never projected to the wire** in `codex_ws.py`. A user configuring `sandbox=read-only` on streaming Codex gets the default sandbox. Silent security downgrade.
- **Duplicate `--allowedTools`** in Claude streaming under `CLAUDECODE`: `streaming_runner.py` merges parent-allowed tools into `spec.extra_args`, then `claude_ws._build_command` also injects `--allowedTools` via `permission_resolver.resolve_flags(HarnessId.CLAUDE)` without deduping. Subprocess has a post-build dedupe pass. Streaming doesn't.
- **The D15-promised projection-side completeness guard was never implemented.** Grep across the tree shows zero matches for `_PROJECTED_FIELDS`. Every HIGH finding above is exactly what D15 was supposed to prevent.
- **CLI arg ordering diverges** between subprocess and streaming in Claude, and the two runners duplicate constants and helpers with no shared core.

These are not independent bugs — they share one root cause: **the refactor named the right abstraction but left every enforcement point optional**. The correct shape is to make the abstraction unbypassable at the type system, at import time, and at runtime.

## Solution — Architectural Shape

The target design commits fully to the transport-neutral spec contract by removing every escape hatch. Five structural decisions drive it:

### 1. Generic-typed adapter + connection pairs

`HarnessAdapter` and `HarnessConnection` become `Generic[SpecT]` with `SpecT = TypeVar("SpecT", bound=ResolvedLaunchSpec)`. Each concrete pair binds its spec subclass:

```python
class ClaudeAdapter(HarnessAdapter[ClaudeLaunchSpec]): ...
class ClaudeConnection(HarnessConnection[ClaudeLaunchSpec]): ...
```

The type checker enforces that `ClaudeConnection.start(config, spec: ClaudeLaunchSpec)` cannot be called with a generic spec. Isinstance branches disappear because the spec type is static. This fixes M1 (isinstance branching) and M2 (base class fallback) by construction — there is no generic `ResolvedLaunchSpec` arriving at a concrete adapter's `start()` anymore.

See [typed-harness.md](typed-harness.md).

### 2. The spec factory is mandatory, not default

`BaseSubprocessHarness.resolve_launch_spec` is deleted. The method becomes abstract on the adapter protocol. An adapter without its own `resolve_launch_spec` fails at class definition time. This fixes M2 by removing the fallback.

The `spawn_manager.py:99` `spec or ResolvedLaunchSpec(prompt=config.prompt)` fallback is deleted. `start_spawn` takes a required spec. Any caller that neglects to construct one fails loudly at the type check, not silently at runtime.

See [launch-spec.md](launch-spec.md).

### 3. Shared projection functions + dual completeness guards

Each harness has one **shared projection function** per transport pair that both subprocess and streaming call:

```python
def project_claude_spec_to_cli_args(spec: ClaudeLaunchSpec) -> list[str]: ...
```

This function is the single place Claude spec fields become CLI args. Subprocess and streaming runners prepend their transport-specific base command (`["claude", "-"]` vs `["claude", "-p", "--input-format", "stream-json", ...]`) and append the result. M3 (arg ordering divergence) vanishes because there is only one ordering. H2 (duplicate `--allowedTools`) vanishes because the projection function is the dedupe site.

Each projection module declares `_PROJECTED_FIELDS: frozenset[str]` and runs an **import-time completeness check** (using a real `ImportError`, not `assert`) that fails if any field on the spec subclass is missing from the projected or ignored set. This is D15, finally implemented, with strip-resistant enforcement.

See [transport-projections.md](transport-projections.md).

### 4. Permission resolver is non-optional end-to-end

`PermissionResolver.config` becomes a **required Protocol property** of type `PermissionConfig`. The getattr-chain fallback in `resolve_permission_config()` is deleted. Every resolver implementation exposes its config directly.

`adapter.resolve_launch_spec(run, perms)` requires a non-None `PermissionResolver`. The two `cast("PermissionResolver", None)` sites fix their call semantics: they either construct a real resolver from context, or they explicitly instantiate a documented `NoOpPermissionResolver` with a visible warning log at construction. Either way, the parameter type is honest and the type checker catches future mistakes.

See [permission-pipeline.md](permission-pipeline.md).

### 5. Shared launch core instead of parallel runner monoliths

Both runners extract their common steps — execution-cwd resolution, Claude preflight, shared constants, env building, spec construction — into a `launch/core.py` module. Each runner becomes a thin orchestrator over `prepare_launch_context(...)` + either subprocess invocation or streaming connection startup + shared drain/finalize.

This resolves M6 (the duplication that got materially worse post-refactor), removes the last source of silent drift between paths, and sets up the ground for the L11 full decomposition as follow-up.

See [runner-shared-core.md](runner-shared-core.md).

## What v1 Got Right (Preserve)

The v1 refactor was directionally correct. The following elements remain in v2 unchanged:

- `ResolvedLaunchSpec` as the transport-neutral contract
- Per-harness spec subclasses (`ClaudeLaunchSpec`, `CodexLaunchSpec`, `OpenCodeLaunchSpec`)
- Strategy map retirement (`FlagEffect`, `FlagStrategy`, `StrategyMap`, `build_harness_command` stay deleted)
- Factory method pattern (`adapter.resolve_launch_spec(params, perms)`)
- `_SPEC_HANDLED_FIELDS` construction-side completeness guard on `SpawnParams`
- Effort normalization inside the factory, not the transport
- `claude_preflight.py` extracted as shared Claude-specific helper
- `ConnectionConfig.model` removed — adapters read model from spec
- Semantic `PermissionConfig` carried on the spec (not CLI-shaped `permission_flags`)

## What v1 Got Wrong (Re-shape)

| v1 behavior | v2 target |
|---|---|
| `BaseSubprocessHarness.resolve_launch_spec` returns generic spec | Deleted. Method becomes abstract on the adapter protocol. |
| `spawn_manager.py:99` `spec or ResolvedLaunchSpec(prompt=...)` | Deleted. `spec` is required. |
| `cast("PermissionResolver", None)` in `streaming_runner.py` and `server.py` | Deleted. Resolver is non-optional; entry points construct one or use `NoOpPermissionResolver` with warning. |
| `isinstance(spec, ClaudeLaunchSpec)` in connection adapters | Deleted. Connections bind spec subclass via `Generic[SpecT]`. |
| `CodexLaunchSpec.sandbox_mode` / `.approval_mode` never projected | Projected to `-c` overrides / CLI flags on the `codex app-server` launch command. |
| Claude streaming lacks `--allowedTools` dedupe | Shared projection function owns dedupe for both paths. |
| `_PROJECTED_FIELDS` not implemented | Declared per-projection; import-time `ImportError` on drift. |
| `report_output_path` on base spec | Moved to `CodexLaunchSpec`. |
| `resolve_permission_config(perms)` getattr fallback chain | Deleted. `PermissionResolver.config` is a required Protocol property. |
| Duplicate constants + preflight across two runners | Extracted to `launch/core.py` + `launch/constants.py`. |
| Claude CLI arg ordering divergence | One shared projection → one canonical ordering. |
| `OpenCodeConnection` does not inherit `HarnessConnection` | Inherits via `HarnessConnection[OpenCodeLaunchSpec]`. |
| OpenCode skills double-injection risk | One authoritative channel (see M4 resolution in transport-projections.md). |
| `_SPEC_HANDLED_FIELDS` uses `assert` (stripped under `-O`) | Replaced with real `ImportError` check. |
| `mcp_tools` in `_SPEC_HANDLED_FIELDS` but handled in env.py | Tracked via a separate `_SPEC_DELEGATED_FIELDS` set with explicit delegation comments. |
| Missing debug log for passthrough args on app-server / serve | Added per M7. |
| Codex confirm-mode rejection not surfaced as event | Emits `HarnessEvent` per M9. |
| Double effort normalization in `claude.py:266-269` | Removed — factory is the single normalization site. |
| `agent_name` duplicated on Claude and OpenCode specs | Moved to a shared mixin or base field since semantics are identical. |
| `dedupe_nonempty` / `split_csv_entries` in `claude_preflight.py` | Moved to `launch/text_utils.py` as generic utilities. |

## Scope

**In scope for this work item:**

- All four HIGH findings (H1-H4) from p1411.
- Medium findings M1-M9.
- Low findings L1, L2, L4, L6, L10 (they fall out naturally from the structural fixes).
- Structural re-shape via `Generic[SpecT]` typing.
- Shared projection function per harness per transport pair.
- Shared `launch/core.py` for preflight + constants + launch context assembly.
- Parity tests covering every spec field, every projection path, every permission mode.

**Out of scope:**

- Full `runner.py` / `streaming_runner.py` decomposition (L11) — deferred to a follow-up refactor once the shared core lands and the review cycle has converged.
- MCP wiring — all adapters still return `None` from `mcp_config()`.
- New harness adapters.
- Interactive/primary launch path changes — focus is on child spawns.

## Enumerated Edge Cases, Failure Modes, Boundary Conditions

Every item in this list has a corresponding scenario file under `scenarios/`. See [edge-cases.md](edge-cases.md) for detailed narratives. Tester roles are indicative — the scenario files are authoritative.

**Type and contract boundaries:**
1. E1 — Adapter subclass omits `resolve_launch_spec` override. Must fail at class definition, not at launch.
2. E2 — Caller constructs a `ResolvedLaunchSpec` base instance and passes it to `ClaudeConnection.start`. Must fail at type check (pyright error) and at runtime (loud guard).
3. E3 — Caller passes `None` as `PermissionResolver` to `adapter.resolve_launch_spec`. Must fail at type check (`None` not assignable).
4. E4 — `PermissionResolver` implementation lacks `.config` property. Must fail at Protocol conformance, not via a silent `getattr` fallback.
5. E5 — New field added to `ClaudeLaunchSpec` but `project_claude_spec_to_cli_args` doesn't project it. Must fail at **import time** via `_PROJECTED_FIELDS` completeness check (not assert, not silent drop).
6. E6 — New field added to `SpawnParams` but `ClaudeAdapter.resolve_launch_spec` doesn't map it. Must fail at import time via `_SPEC_HANDLED_FIELDS` check (not assert).

**Permission flow:**
7. E7 — Streaming Codex launched with `sandbox=read-only`. Must project to `-c sandbox_mode="read-only"` (or the `--sandbox` flag supported by `codex app-server`). Verified via debug trace.
8. E8 — Streaming Codex launched with `approval=auto`. Must accept-all with no confirm gate. Verified via JSON-RPC trace.
9. E9 — Streaming Codex launched with `approval=default`. Must use the harness default (not force auto-accept). Verified via JSON-RPC trace.
10. E10 — Streaming Codex launched with `approval=confirm`. Must reject approvals and emit `HarnessEvent("warning/approvalRejected", ...)` before returning the JSON-RPC error. Verified via event stream.
11. E11 — Streaming Claude launched with `ExplicitToolsResolver` granting `["Read", "Edit"]` AND parent-env `--allowedTools Read,Bash`. Final command must contain exactly one `--allowedTools` flag with the deduped union `Read,Edit,Bash`. Verified via command snapshot.
12. E12 — Subprocess Claude run through the full happy path. Final command must contain exactly one `--allowedTools` flag with identical contents to E11's streaming command (parity contract).
13. E13 — REST server POST with no permission block. Spawn must succeed with a `NoOpPermissionResolver` and emit a `warning: permissions omitted` log. No silent zero-flag emission.
14. E14 — `run_streaming_spawn()` invoked with a caller-provided resolver. Resolver must reach the adapter factory; no cast-to-None and no default swap.

**Spec-to-wire projection completeness:**
15. E15 — Claude spec carries `appended_system_prompt`, `agents_payload`, `agent_name`, `continue_session_id`, `continue_fork`. Every field must appear in both subprocess and streaming commands in identical order.
16. E16 — Codex spec carries `sandbox_mode`, `approval_mode`, `effort`. All three must reach both the `codex exec --json` CLI (subprocess) and the `codex app-server` launch args / JSON-RPC session bootstrap (streaming). Parity asserted by test.
17. E17 — OpenCode spec carries `model`, `agent_name`, `skills`, `effort` (unsupported by HTTP API per D16), `continue_session_id`. Model prefix normalization runs once in the factory. Streaming HTTP projection logs debug-level warning when projecting unsupported fields.
18. E18 — OpenCode skills. One authoritative channel. Either `run_prompt_policy.include_skills=False` for streaming (rely on HTTP payload) or HTTP payload drops `skills` (rely on prompt inlining). Decision made after verifying OpenCode HTTP API semantics. Tester verifies no double injection.
19. E19 — `report_output_path` set on a Codex spawn. Subprocess projects to `-o <path>`. Streaming projects to nothing and emits a debug log (documented Codex-only field, documented streaming-no-support).
20. E20 — `continue_fork=True` with `continue_session_id=None`. Must either raise in spec construction or be silently ignored — decided in the factory, tested end-to-end.

**CLI arg ordering:**
21. E21 — Claude subprocess and streaming paths produce identical arg ordering for the same spec (modulo the base command prefix). Parity test asserts byte-equal projected args list.
22. E22 — User passes `--append-system-prompt "custom"` via `extra_args` while Meridian also wants to set `--append-system-prompt`. Canonical policy: Meridian's value wins, user's passthrough is dropped with a warning. Same behavior on both paths.
23. E23 — User passes `--allowedTools A,B` via `extra_args` while resolver emits `--allowedTools C,D`. Canonical policy: deduped union `A,B,C,D` appears once. Same behavior on both paths.

**Runner shared core:**
24. E24 — Subprocess and streaming runners call `prepare_launch_context(plan, run_params, perms)` with identical inputs. Resulting context must be byte-identical (same env, same cwd, same spec, same preflight state).
25. E25 — Parent Claude permissions forwarded via `CLAUDECODE`. Both runners use the same `read_parent_claude_permissions` + `merge_allowed_tools_flag` pipeline via the shared core. No duplication.
26. E26 — Constants (timeouts, default ports, blocked env vars, base commands) live in one module. Grep shows no duplicate definitions across runners.

**Environment and OS-level:**
27. E27 — `python -O` runs the full test suite. Every completeness guard still fires (using `ImportError`, not `assert`).
28. E28 — Claude CLI not on PATH. Both runners fail with the same structured error.
29. E29 — `codex app-server` binary rejects passthrough args. Streaming runner emits a debug-level warning before launch.

**Type and import ordering:**
30. E30 — `_PROJECTED_FIELDS` completeness check runs at module import (not at first call). Adding a spec field then running any import of the projection module raises `ImportError` immediately.
31. E31 — Circular import risk: `launch_spec.py` imports `PermissionResolver` and `SpawnParams`; projection modules import `launch_spec`. Verified acyclic.

**Event stream / observability:**
32. E32 — Codex confirm-mode rejection surfaces as `HarnessEvent("warning/approvalRejected", {"reason": "confirm_mode", "method": method})` on the event queue before returning the JSON-RPC error.
33. E33 — Streaming runner logs a debug-level message listing any passthrough args being forwarded to `codex app-server` / `opencode serve`.

**Connection protocol conformance:**
34. E34 — `OpenCodeConnection` inherits from `HarnessConnection[OpenCodeLaunchSpec]` so Protocol signature drift is caught statically.
35. E35 — `ClaudeConnection`, `CodexConnection`, `OpenCodeConnection` all expose the same `state`, `health`, `events()`, `send_user_message`, `stop` surface — verified by instantiating each against the Protocol.

Every numbered item has a scenario file. See `scenarios/overview.md` for the master index.

## Success Criteria

- Every `SpawnParams` field reaches every harness correctly through both subprocess and streaming paths.
- Adding a new field to `SpawnParams` or any spec subclass fails visibly at import time or type-check time — never silently at runtime.
- Zero silent fallbacks. A caller that misuses the API gets a loud error, not wrong behavior.
- Permission resolution reaches every entry point. No `cast("PermissionResolver", None)`. No `getattr(perms, "config", None)` fallback chain.
- One shared projection function per harness per transport pair. Subprocess and streaming cannot drift on arg ordering or field coverage.
- Dual runner growth reversed. Shared `launch/core.py` owns preflight, constants, env building, and launch-context assembly.
- Post-impl multi-model review on v2 finds no structural findings in the same class as H1-H4 or M1-M9.
