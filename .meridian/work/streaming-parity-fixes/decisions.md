# Decisions — Streaming Parity Fixes (v2)

This log captures the v2 architectural decisions made during the design phase. Each decision states what was decided, why, what was rejected, and which v1 finding or requirement it addresses. v1 decisions are in `../work-archive/streaming-adapter-parity/decisions.md`; this log only records deltas from v1 or decisions that v1 did not make explicit.

---

## D1 — Generic type binding via `TypeVar("SpecT", bound=ResolvedLaunchSpec)`

**Decision.** `HarnessAdapter[SpecT]` and `HarnessConnection[SpecT]` are parameterized over a `TypeVar("SpecT", bound=ResolvedLaunchSpec)`. Each concrete adapter and connection declares its own spec type at the class level (e.g., `class ClaudeConnection(HarnessConnection[ClaudeLaunchSpec])`).

**Why.** v1 had `HarnessConnection.start(spec: ResolvedLaunchSpec)` with no type parameter, which is why `spawn_manager.py:99` could legally fall back to `ResolvedLaunchSpec(prompt=config.prompt)` and pass it to any connection. Typing `SpecT` makes the mismatch a pyright error at the call site. It also gives reviewers and refactor tooling a mechanical way to know which projection belongs to which spec type.

**Rejected alternatives.**
- *One big union type `Union[ClaudeLaunchSpec, CodexLaunchSpec, OpenCodeLaunchSpec]` with exhaustive isinstance.* Keeps the `isinstance` branching inside every connection — exactly the M1 pattern we are trying to delete. The whole point of v2 is removing those branches.
- *Runtime-only type tagging (e.g., `spec.harness_kind`).* Runtime tagging does not help pyright catch drift at compile time, and the v1 experience proved runtime checks are easily bypassed by `cast` or a forgotten branch.

**Addresses.** p1411 M1, M2, H4 (in combination with D5).

---

## D2 — `HarnessBundle` as the paired registry entry

**Decision.** Replace the v1 adapter-keyed registry with a `HarnessBundle(Generic[SpecT])` dataclass carrying `(adapter: HarnessAdapter[SpecT], connection_cls: type[HarnessConnection[SpecT]], spec_cls: type[SpecT])`. The registry maps harness name → bundle. There is **exactly one** `cast` declared at the dispatch boundary, and it is the only cast in the harness layer.

**Why.** v1 separated adapter lookup from connection lookup, so nothing enforced that a given adapter's output spec would actually be accepted by the registered connection. Bundling them makes the three-way invariant explicit. The single declared cast at dispatch is the narrow waist — every call site downstream of dispatch is fully typed.

**Rejected alternatives.**
- *Keep adapter and connection registries separate but add runtime isinstance assertions.* Preserves drift risk (the registries can be inconsistent). Tries to solve a typing problem at runtime.
- *Reflection-based bundle assembly at import time.* More magic, harder to read, no meaningful benefit over the explicit dataclass.

**Addresses.** p1411 M2, M8.

---

## D3 — Remove `BaseSubprocessHarness.resolve_launch_spec` default

**Decision.** `BaseSubprocessHarness` no longer provides a default `resolve_launch_spec` implementation. `resolve_launch_spec` is declared abstract (via `@abstractmethod` on the ABC or via `HarnessAdapter[SpecT]` Protocol conformance). Every concrete adapter must define its own.

**Why.** v1's default returned a generic `ResolvedLaunchSpec`, which hid the booby trap surfaced by p1411 M2: a new adapter could be wired up and silently produce generic specs that fell through to isinstance branches. Making this abstract turns "forgot to override" into an instantiation-time `TypeError`, caught before any spawn runs.

**Rejected alternatives.**
- *Keep the default but have it raise.* Subtly worse — the error would surface at spawn time (not class-construction time), and the trap would still tempt a future developer.
- *Make `resolve_launch_spec` a `@property` that returns a callable.* Harder to type, no benefit.

**Addresses.** p1411 M2, E1.

---

## D4 — `PermissionResolver` is non-optional and `.config` is a required Protocol property

**Decision.** `PermissionResolver` is a `runtime_checkable Protocol` whose members include `resolve_flags(...)` AND a required `config: PermissionConfig` property. Every adapter signature is `resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT`. There is no optional `perms: PermissionResolver | None` anywhere in the stack.

**Why.** v1 used `cast("PermissionResolver", None)` in two sites (`streaming_runner.py:457`, `server.py:203`) — the cast was required precisely because the type allowed `None`. Promoting `.config` to a required Protocol member and making every signature non-optional means the `cast` sites cannot be rebuilt: pyright rejects them. Lenient callers must construct a real `NoOpPermissionResolver`.

**Rejected alternatives.**
- *Keep `PermissionResolver | None` and add a `_coalesce_perms(perms)` helper that wraps None.* Delegates the cast-hiding to a helper function — same bug, different layer. The type system still permits None at the call sites, which means future code can reintroduce the pattern.
- *Make `.config` optional.* Defeats the point; `resolve_permission_config(perms)` would still need the getattr fallback.

**Addresses.** p1411 H3, L6.

---

## D5 — Import-time projection completeness guards via `ImportError`

**Decision.** Every projection module (`projections/claude.py`, `projections/codex.py`, `projections/opencode.py`) declares a module-level `_PROJECTED_FIELDS: frozenset[str]` and a guard block at module scope:

```python
_expected = {name for name in ClaudeLaunchSpec.model_fields} - _SPEC_DELEGATED_FIELDS
_missing = _expected - _PROJECTED_FIELDS
if _missing:
    raise ImportError(
        f"ClaudeLaunchSpec fields not projected: {sorted(_missing)}. "
        "Add them to projections/claude.py::_PROJECTED_FIELDS and handle them in project_claude_spec_to_cli_args."
    )
```

**Why.** v1 promised D15 (a projection completeness check) but never shipped it — which is exactly the gap that let H1 (sandbox/approval dropped from streaming Codex) ship. An import-time guard means a future developer who adds a field to `ClaudeLaunchSpec` and forgets to update the projection cannot even run `meridian --help` without hitting the error. Import-time is the earliest detection point. `ImportError` (not `assert`) is required because `python -O` strips assertions — L1.

**Rejected alternatives.**
- *Use `assert` and rely on tests.* v1 tried this pattern elsewhere (`launch_spec.py` L1). Assertions are stripped under `-O`, and the drift can still ship if the tests are not exhaustive.
- *Use a pytest plugin that scans on test collection.* Runs too late — a developer who runs `meridian` without running the tests first could push code that fails in production.
- *Use a runtime check inside the projection function.* Fires only when the field is non-None; silent drift for fields defaulting to None.

**Addresses.** p1411 H4, L1, E5, E6, E27, E30.

---

## D6 — `_SPEC_HANDLED_FIELDS` + `_SPEC_DELEGATED_FIELDS` in `launch_spec.py`

**Decision.** `launch_spec.py` declares two frozensets:
- `_SPEC_HANDLED_FIELDS`: `SpawnParams` fields the factory maps to concrete spec fields.
- `_SPEC_DELEGATED_FIELDS`: `SpawnParams` fields intentionally handled outside the spec pipeline (e.g., `prompt_mode` controls factory behavior; `mcp_tools` is forwarded as-is).

An import-time guard compares `SpawnParams.model_fields` against the union and raises `ImportError` on drift.

**Why.** v1's `_SPEC_HANDLED_FIELDS` set included `mcp_tools` as a lie (L2) — the field was listed but the factory did nothing with it. Splitting into "handled" and "delegated" makes the lie impossible: if a field is delegated, it must be named in the set, and the developer must look at it consciously. The guard forces new `SpawnParams` fields into one of the two sets.

**Rejected alternatives.**
- *Single `_SPEC_HANDLED_FIELDS` set.* v1 did this. Encouraged the L2 lie.
- *Per-adapter "handled" sets.* Moves the drift-detection problem into every adapter. v2's approach keeps it centralized in `launch_spec.py`.

**Addresses.** p1411 L2, E6.

---

## D7 — Shared projection functions per harness

**Decision.** Each harness has exactly one projection function shared by subprocess and streaming paths:
- `project_claude_spec_to_cli_args(spec: ClaudeLaunchSpec, base: tuple[str, ...]) -> list[str]`
- `project_codex_spec_to_cli_args(spec: CodexLaunchSpec, base: tuple[str, ...]) -> list[str]` (subprocess)
- `project_codex_spec_to_appserver_command(spec: CodexLaunchSpec) -> list[str]` (streaming)
- `project_opencode_spec_to_cli_args(spec: OpenCodeLaunchSpec, base: tuple[str, ...]) -> list[str]` (subprocess)
- `project_opencode_spec_to_http_payload(spec: OpenCodeLaunchSpec) -> dict` (streaming)

Claude uses one function for both paths (same CLI binary, different base). Codex and OpenCode have distinct wire formats per transport, so they have distinct projections — but both projections share the same spec type, the same completeness guard, and the same helper utilities (arg merging, permission-flag emission).

**Why.** v1 split Claude into two functions and M3 found they drifted (different arg orderings between subprocess and streaming). Codex and OpenCode have genuinely different wire formats, so splitting is appropriate — but the completeness guard must apply equally to both.

**Rejected alternatives.**
- *One projection per harness regardless of transport.* Forces Codex subprocess and Codex app-server into a common shape that does not exist in reality. Would make the function full of transport branches — the exact anti-pattern we deleted from the connections.
- *One projection per transport per harness (6 functions).* Splits Claude's subprocess and streaming paths, guaranteeing the M3 drift bug returns.

**Addresses.** p1411 M3, H4.

---

## D8 — `--allowedTools` dedupe happens at the projection site

**Decision.** `project_claude_spec_to_cli_args` internally calls `_merge_allowed_tools(perm_flags, extra_args)` which emits exactly one `--allowedTools` flag containing the deduped union in canonical order. Neither the runner nor the preflight code emits `--allowedTools` directly to `extra_args`.

**Why.** v1 H2 arose because the streaming runner applied `merge_allowed_tools_flag` to passthrough args pre-projection, then the connection injected another `--allowedTools` via `resolve_flags`, and no final dedupe existed. Putting dedupe inside the shared projection means the contract is: "by the time the projection returns, there is exactly one `--allowedTools` flag in the result." Both runners get this for free.

**Rejected alternatives.**
- *Runner-level dedupe post-projection.* Requires every runner to remember to do it. v1 subprocess did; v1 streaming did not; the bug happened.
- *Preflight-level dedupe with no projection-level guard.* Same problem — future runners can forget.

**Addresses.** p1411 H2, E11, E12, E23.

---

## D9 — Canonical Claude arg ordering

**Decision.** `project_claude_spec_to_cli_args` emits flags in a canonical order:
1. Base command (`claude` or `claude --output-format stream-json`)
2. `--model`
3. `--effort`
4. `--agent`
5. `--append-system-prompt`
6. `--agents`
7. `--resume` / `--fork-session`
8. Permission flags merged with extra_args (deduped on `--allowedTools`, `--disallowedTools`)
9. Any remaining extra_args preserving their original order

**Why.** v1 had different orders on subprocess vs streaming (M3) because each runner built the command ad-hoc. One canonical order, enforced by one projection, means subprocess and streaming are byte-equal past the base command — which is the parity contract in executable form (S021).

**Rejected alternatives.**
- *Alphabetical order.* Breaks Claude's semantics where `--append-system-prompt` and `--allowedTools` are order-sensitive for last-wins.
- *User-extensible order via config.* YAGNI; no user has asked for this, and it reintroduces divergence risk.

**Addresses.** p1411 M3, E15, E21.

---

## D10 — `_AgentNameMixin` for shared `agent_name` field

**Decision.** The `agent_name` field is lifted into a `_AgentNameMixin` mixin. Both `ClaudeLaunchSpec` and `CodexLaunchSpec` inherit from it (and `ResolvedLaunchSpec`). The mixin owns the Pydantic field declaration, validation, and default.

**Why.** v1 declared `agent_name` on both subclasses independently, with slightly different defaults. A mixin keeps the declaration DRY and prevents drift. It also gives pyright one place to find the field's definition when navigating.

**Rejected alternatives.**
- *Promote `agent_name` into `ResolvedLaunchSpec` base.* Pollutes OpenCode (which does not use `agent_name`). The mixin is a narrower contract.
- *Repeat in both subclasses with a matching test.* v1 pattern. Tests catch drift late; structure prevents it.

**Addresses.** p1411 L5.

---

## D11 — `NoOpPermissionResolver` with loud construction-time warning

**Decision.** Introduce `NoOpPermissionResolver` as a concrete class implementing `PermissionResolver`. Its `config` property returns `PermissionConfig(sandbox="default", approval="default")`. Its `resolve_flags` returns `[]`. Its `__init__` emits a loud WARNING log: "NoOpPermissionResolver constructed — no permission enforcement will be applied".

**Why.** The server and streaming runner need a way to opt out of permissions without the v1 cast-to-None trick. An explicit class with a loud warning is the honest opt-out: the code is self-documenting, the log is auditable, and the usage is grep-able (`rg NoOpPermissionResolver`).

**Rejected alternatives.**
- *Sentinel singleton (`PERMISSIONS_DISABLED`).* Hides the pattern behind a magic constant. The construction-time warning is harder to attach.
- *Default-parameter `perms: PermissionResolver = NoOpPermissionResolver()`.* Shared mutable default is a Python footgun and encourages silent opt-out. Requiring explicit construction at call sites forces the developer to look at the log call.

**Addresses.** p1411 H3, L6.

---

## D12 — `LaunchContext` + `prepare_launch_context()` shared helper

**Decision.** Introduce a frozen dataclass `LaunchContext(spec, env, run_params, child_cwd, env_overrides)` and a helper `prepare_launch_context(plan, ...) -> LaunchContext`. Both `runner.py` and `streaming_runner.py` call it to produce the context before handing off to subprocess.launch or connection.start.

**Why.** v1 M6 identified that the two runners built env and cwd independently, with subtle divergence. A single helper with a single return type forces parity. Frozen dataclass means once constructed, the context cannot be mutated — reviewers and testers can trust that a `LaunchContext` is the single source of truth for a given launch.

**Rejected alternatives.**
- *Keep separate helpers, add a parity test.* Tests catch drift late; the parallel implementations are the real problem.
- *Full runner decomposition (split runner.py into small modules).* Correct direction but L11-scale; deferred to a follow-up refactor to keep this scope bounded.

**Addresses.** p1411 M6, E24, E25.

---

## D13 — Constants to `launch/constants.py`

**Decision.** Move `DEFAULT_*_SECONDS`, `DEFAULT_INFRA_EXIT_CODE`, `_BLOCKED_CHILD_ENV_VARS`, and the per-harness `BASE_COMMAND` tuples into `src/meridian/lib/launch/constants.py`. Both runners import from this module.

**Why.** v1 M6 also noted duplicate constant definitions. Centralizing them means one grep-able definition site, one changeset to update a timeout, and no possibility of drift.

**Rejected alternatives.**
- *Per-runner constants with a linter check.* Adds process without removing duplication.
- *Per-harness constants in each adapter.* The constants are cross-harness (timeouts, blocked env) or cross-transport (base commands), so per-harness placement does not fit.

**Addresses.** p1411 M6, E26.

---

## D14 — Approval rejection emits `HarnessEvent` before JSON-RPC error

**Decision.** When `codex_ws` rejects an approval request under `confirm` mode, it enqueues `HarnessEvent(kind="warning/approvalRejected", data={"reason": "confirm_mode", "method": method, "request_id": id})` to the event queue BEFORE writing the JSON-RPC error response frame.

**Why.** v1 M9: the confirm-mode rejection was logged but not emitted as a structured event. Consumers watching the event stream only learned about it via downstream session failure. Emitting the event inline is the observable primitive the consumer needs.

**Rejected alternatives.**
- *Log-only (v1).* Opaque to programmatic consumers.
- *Emit after the error response.* Introduces an ordering race where the downstream failure can be observed before the cause event.

**Addresses.** p1411 M9, E10, E32.

---

## D15 — Codex streaming reads sandbox/approval from `permission_resolver.config` directly

**Decision.** `CodexLaunchSpec` does **not** store `sandbox_mode` or `approval_mode` as independent fields. The projection reads them from `spec.permission_resolver.config.sandbox` and `.config.approval` at projection time and emits `-c sandbox_mode=<v>` / `-c approval_policy=<v>` (or the verified-at-impl equivalent) into the `codex app-server` launch command.

**Why.** v1 H1 shipped because the `CodexLaunchSpec` fields existed but nobody read them — the `codex_ws` implementation dropped them. v2 eliminates the redundant fields: the resolver's config is the single source of truth, and the projection is the single consumer. There is nowhere for a developer to "forget to read" because the fields do not exist.

**Rejected alternatives.**
- *Keep the fields and add a runtime assertion that they match the resolver.* Two sources of truth, synchronization problem, assertion-strippable.
- *Store a denormalized copy on the spec.* Same problem in a different shape.

**Addresses.** p1411 H1, M1.

---

## D16 — `report_output_path` lives on `CodexLaunchSpec`, not base

**Decision.** `report_output_path` is declared on `CodexLaunchSpec` only. The base `ResolvedLaunchSpec` does not carry it.

**Why.** It is a Codex-only concept (`-o` flag on `codex exec`). v1 had it on the base class, polluting Claude and OpenCode with a field that was meaningless to them. On streaming Codex, the projection ignores it (with a debug log — S019) because `codex app-server` has no equivalent flag; the runner extracts reports from artifacts.

**Rejected alternatives.**
- *Leave on base "for future harnesses".* YAGNI and pollutes two current harnesses.
- *Move to a `CodexSpecificFields` mixin.* Unnecessary indirection for a one-field mixin.

**Addresses.** p1411 M5.

---

## D17 — OpenCode skills single-injection policy at spec construction

**Decision.** The adapter factory decides the skills delivery path at spec construction time:
- If `run_prompt_policy().include_skills is True`: prompt inlines skills, `spec.skills = ()`.
- Otherwise: prompt does not inline, `spec.skills = (...original tuple...)`, projection carries skills in the HTTP payload / CLI flag.

There is no runtime branch in the projection to choose between paths — the choice is locked in the spec.

**Why.** v1 M4 identified a risk that OpenCode could deliver skills twice (once inlined, once via the HTTP payload). Making the choice at spec-construction time means the spec itself is the single source of truth; both transports respect `spec.skills` without needing to coordinate with the prompt builder.

**Rejected alternatives.**
- *Runtime branch in the projection.* Same coordination bug waiting to happen.
- *Always inline.* Forfeits the HTTP-payload path's flexibility.

**Addresses.** p1411 M4, E18.

---

## D18 — `OpenCodeConnection` must inherit `HarnessConnection[OpenCodeLaunchSpec]`

**Decision.** `OpenCodeConnection` is declared as `class OpenCodeConnection(HarnessConnection[OpenCodeLaunchSpec]):`. The v1 `class OpenCodeConnection:` (no base) is rejected.

**Why.** v1 M8: `OpenCodeConnection` duck-typed its way into the Protocol. When `HarnessConnection` evolves (new abstract method), pyright has no leverage to force `OpenCodeConnection` to implement it. Explicit inheritance gives the type system the leverage.

**Rejected alternatives.**
- *Runtime `runtime_checkable` Protocol conformance check.* Catches at runtime, not at compile time, and pyright cannot see through the duck.
- *Register `OpenCodeConnection` with the Protocol via `Protocol.register`.* Does not exist in Python; Protocols are structural.

**Addresses.** p1411 M8, E34, E35.

---

## D19 — Full runner decomposition (L11) deferred

**Decision.** v2 does NOT attempt to split `runner.py` / `streaming_runner.py` into small modules per concern. The scope is: extract the shared core (LaunchContext, constants), delete the duplication, and ship. L11's broader decomposition is a follow-up refactor.

**Why.** Scope control. The v1 review flagged the runners as "too big" but v2's goal is closing the HIGH/MEDIUM findings from p1411 without opening a new structural refactor. A full decomposition inside this work item risks not shipping any of the H-level fixes. The `LaunchContext` extraction is the minimum viable split that addresses M6; the rest can follow once v2 is in the tree.

**Rejected alternatives.**
- *Full decomposition now.* High risk of not converging.
- *No extraction at all.* Leaves M6 unfixed.

**Addresses.** Scope discipline for H1–H4 + M-series.

---

## D20 — Probe `codex app-server --help` before committing to flag names

**Decision.** The implementation for D15 (Codex sandbox/approval projection) MUST begin by running `codex app-server --help` against the real binary and recording the observed flag names and syntax in the design decision log (appended below this entry at implementation time). Only after that probe is complete does the coder write the projection.

**Why.** v1 H1 shipped partly because the adapter was written against assumed flag names rather than observed ones. The dev-principles "Probe Before You Build at Integration Boundaries" rule applies directly. Recording the probe result in the decision log gives reviewers a verifiable anchor.

**Rejected alternatives.**
- *Guess based on `codex exec --help`.* Exactly the v1 failure mode.
- *Probe but don't record.* Loses the audit trail.

**Addresses.** dev-principles integration-boundary rule, p1411 H1 root cause.
