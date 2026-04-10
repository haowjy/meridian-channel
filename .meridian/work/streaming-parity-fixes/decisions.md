# Decisions — Streaming Parity Fixes (v2)

## D1 — Generic binding with runtime-checked dispatch narrow

**Decision.** Use `SpecT`-bound generic adapters/connections and a single dispatch-site runtime guard:

- `if not isinstance(spec, bundle.spec_cls): raise TypeError(...)`
- then `cast(SpecT, spec)` for `connection.start(...)`

**Why.** Removes silent runtime drift while keeping one explicit narrow boundary.

**Addresses.** M1, M2, S002.

## D2 — `HarnessBundle` paired registry

**Decision.** Registry entries pair `adapter`, `connection_cls`, and `spec_cls` for each `HarnessId`.

**Why.** Keeps dispatch invariant explicit and auditable.

**Addresses.** M2, M8.

## D3 — Abstract factory enforcement is ABC + Protocol

**Decision.** `HarnessAdapter` remains Protocol for static structural checks, and `BaseSubprocessHarness(Generic[SpecT], ABC)` declares `@abstractmethod resolve_launch_spec(...)` for runtime instantiation rejection.

**Why.** Protocol conformance alone does not raise instantiation-time `TypeError`.

**Addresses.** E1, S001.

## D4 — Non-optional resolver contract

**Decision.** `PermissionResolver` is non-optional and requires `.config`.

**Why.** Deletes cast-to-None entry points and silent fallback chains.

**Addresses.** H3.

## D5 — Projection drift guard (both directions)

**Decision.** Use import-time helper `_check_projection_drift(...)` and compare expected vs accounted fields in both directions.

```python
expected = set(spec_cls.model_fields)
accounted = projected | delegated
if expected != accounted:
    missing = expected - accounted
    stale = accounted - expected
    raise ImportError(f"Projection drift: missing={sorted(missing)} stale={sorted(stale)}")
```

**Why.** Catches both newly added fields and stale removed names.

**Addresses.** H4, L1.

## D6 — SpawnParams accounting split

**Decision.** Keep `_SPEC_HANDLED_FIELDS` + `_SPEC_DELEGATED_FIELDS` accounting in `launch_spec.py`.

**Why.** Forces explicit ownership for every `SpawnParams` field.

**Addresses.** L2.

## D7 — Projection function set and naming

**Decision.** Standardize projection modules/functions:

- `project_claude.py`
- `project_codex_subprocess.py`
- `project_codex_streaming.py`
- `project_opencode_subprocess.py`
- `project_opencode_streaming.py`

Use `project_opencode_spec_to_session_payload` (not `...http_payload`).
Keep reserved-flag constants and stripping helper centralized in `src/meridian/lib/harness/projections/_reserved_flags.py`.

**Why.** Consistent axis and lower blast radius.

**Addresses.** M3, M4, F9, F28, F35.

## D8 — Claude permission-flag dedupe at projection site

**Decision.** Deduplicate/merge `--allowedTools` and `--disallowedTools` in Claude projection.

**Why.** One authoritative merge point across transports.

**Addresses.** H2.

## D9 — Canonical Claude ordering

**Decision.** One canonical projection order for subprocess and streaming Claude tails.

**Why.** Prevents transport ordering drift.

**Addresses.** M3.

## D10 — `agent_name` declaration scope

**Decision.** Inline `agent_name: str | None = None` directly on `ClaudeLaunchSpec` and `OpenCodeLaunchSpec`; do not keep a shared mixin at two call sites.

**Why.** Abstraction threshold not met (2 consumers). Re-extract only when a third semantically aligned consumer exists.

**Addresses.** L3 (not L5).

## D11 — `UnsafeNoOpPermissionResolver`

**Decision.** Rename `NoOpPermissionResolver` to `UnsafeNoOpPermissionResolver`; retain loud warning semantics.

**Note.** Unit tests may pass `_suppress_warning=True` to reduce fixture noise.

**Why.** Name must encode risk; unsafe behavior must be explicit.

**Addresses.** H3, F10, F36, F37.

## D12 — Shared `LaunchContext`

**Decision.** Both runners call `prepare_launch_context(...)` from `launch/context.py`.

**Why.** Centralizes launch-state assembly and removes runner duplication.

**Addresses.** M6.

## D13 — Constants/text util extraction

**Decision.** Shared constants live in `launch/constants.py`; shared text helpers (`dedupe_nonempty`, `split_csv_entries`) live in `launch/text_utils.py`.

**Why.** Closes per-harness utility duplication and addresses L5 smell.

**Addresses.** M6, L5.

## D14 — Confirm-mode event ordering semantics

**Decision.** Guarantee is: rejection event is enqueued before `send_error` is awaited.

**Why.** Deterministic call ordering without wall-clock assumptions.

**Addresses.** M9, S032.

## D15 — Codex spec shape

**Decision.** `CodexLaunchSpec` does not store `sandbox_mode` or `approval_mode`; projections read `spec.permission_resolver.config` directly.

**Why.** Removes duplicate state and H1-style stale field hazards.

**Addresses.** H1.

## D16 — `report_output_path` on Codex only

**Decision.** Keep `report_output_path` only on `CodexLaunchSpec`.

**Why.** Harness-specific feature.

**Addresses.** M5.

## D17 — OpenCode skills single-channel policy

**Decision.** Skills delivery channel is chosen at spec construction; projections do not choose channel dynamically.

**Why.** Avoid double-injection.

**Addresses.** M4.

## D18 — OpenCode connection inheritance

**Decision.** `OpenCodeConnection` inherits `HarnessConnection[OpenCodeLaunchSpec]`.

**Why.** Keep interface drift visible to type system.

**Addresses.** M8.

## D19 — Runner size budget + trigger

**Decision.** Full decomposition remains out of v2 scope, but post-v2 budget is mandatory:

- `runner.py <= 500` lines
- `streaming_runner.py <= 500` lines

If either exceeds budget after v2, raise L11 decomposition back into active scope immediately.

**Why.** Enforces structural health signal, avoids indefinite deferral.

**Addresses.** M6/L11 follow-through.

## D20 — Codex probe and fail-closed capability policy

**Decision.** Probe real `codex app-server --help` before finalizing mapping. If requested sandbox/approval semantics cannot be expressed, projection raises `HarnessCapabilityMismatch` and spawn fails before launch.

**Why.** No silent downgrade at integration boundary.

**Addresses.** H1, E38.

## D21 — Adapter-owned preflight contract

**Decision.** Add `preflight(...) -> PreflightResult` to `HarnessAdapter`; base returns empty result; Claude overrides for parent-permission forwarding and `--add-dir` injection.

**Why.** Removes harness-id branching from shared launch context and preserves Open/Closed boundaries.

**Addresses.** F5.

## D22 — Connection facet collapse

**Decision.** Remove `HarnessLifecycle` / `HarnessSender` / `HarnessReceiver` facet protocols in v2; keep single `HarnessConnection[SpecT]` ABC.

**Why.** Avoid duplicate interface declarations drifting out of sync.

**Audit.** `rg "HarnessLifecycle|HarnessSender|HarnessReceiver" src/` showed negligible consumer value for keeping facets.

**Addresses.** F20.

## D23 — Remove `mcp_tools` from `SpawnParams` in v2

**Decision.** Delete `mcp_tools` from launch-time spec/factory surface for v2.

**Why.** MCP wiring is explicitly out of scope and current adapters return no MCP config.

**Addresses.** F30.

## D24 — Shared missing-binary error class

**Decision.** Introduce `HarnessBinaryNotFound` in `src/meridian/lib/harness/errors.py` and use it across subprocess and streaming runners.

**Why.** Structured parity for PATH/binary failures.

**Addresses.** F33, S028.

## Revision Pass 1 (post p1422/p1423/p1425/p1426)

- F1: Unified `CodexLaunchSpec` shape; removed sandbox/approval fields from launch-spec examples and added D15 supersession note.
- F2: Updated Codex projection field sets to post-D15 shape and added resolver-config read example.
- F3: Clarified Protocol vs ABC roles; abstract-method instantiation enforcement now explicitly ABC-based.
- F4: Replaced `cast(Any, spec)` guidance with dispatch `isinstance` guard plus `cast(SpecT, spec)`.
- F5: Added adapter `preflight` contract and moved Claude preflight ownership behind adapter boundary.
- F6: Expanded completeness model to transport-wide accounted-field unions across all consumers.
- F7: Added reserved-flag policy and passthrough stripping/merge semantics with warning logs.
- F8: Added fail-closed Codex capability mismatch policy for unrepresentable sandbox/approval semantics.
- F9: Merged Codex streaming projections into `project_codex_streaming.py`.
- F10: Switched REST default to strict rejection; unsafe fallback gated by `--allow-unsafe-no-permissions`.
- F11: Corrected D5 sample to check both missing and stale drift directions.
- F12: Corrected D10 finding label to L3; documented L5 closure via text-utils extraction.
- F13: Reconciled S002 contract with dispatch-site runtime guard and no behavior-switching checks in connections.
- F14: Updated scenario module enumeration to full renamed projection module set and added `_PROJECTED_FIELDS` match-count meta assertion.
- F15: Corrected S033 OpenCode target function to `project_opencode_spec_to_serve_command`.
- F16: Added Codex streaming debug log for ignored `report_output_path` and delegated-field annotation.
- F17: Made continue-fork validator base-scoped so it applies to all harness specs.
- F18: Standardized guard testing on `_check_projection_drift` helper with synthetic spec classes.
- F19: Added `launch_types.py` DAG topology and moved shared leaf contracts there.
- F20: Chose facet collapse; connection surface is now single ABC contract.
- F21: Audited typed design guidance to remove `cast(Any, ...)` in favor of typed narrow casts.
- F22: Set authoritative cast location to `SpawnManager.start_spawn`; removed conflicting shared-core wording.
- F23: Reframed S016 requirement to semantic distinctness plus audit trail (not distinct wire strings per cell).
- F24: Declared `PermissionConfig.approval` as a `Literal` domain.
- F25: Tightened confirm-mode ordering guarantee to enqueue-before-await semantics.
- F26: Reconciled append-system-prompt policy to "both flags appear; user wins; warning emitted".
- F27: Added post-v2 runner line-budget target (500 each) with explicit L11 trigger.
- F28: Renamed projection modules to consistent `project_<harness>_<transport>.py` pattern.
- F29: Renamed shared launch module reference from `launch/core.py` to `launch/context.py`.
- F30: Removed `mcp_tools` from v2 launch spec/factory surface and documented decision.
- F31: Documented `_SPEC_HANDLED_FIELDS` limitation (global accounting, not per-adapter completeness).
- F32: Added explicit `BaseSubprocessHarness` default-method audit requirement in typed migration shape.
- F33: Added explicit `HarnessBinaryNotFound` structured error decision.
- F34: Tightened S015 verification to require explicit field-to-wire mapping table assertions.
- F35: Standardized OpenCode session payload function name to `project_opencode_spec_to_session_payload`.
- F36: Renamed all design/scenario references from `NoOpPermissionResolver` to `UnsafeNoOpPermissionResolver`.
- F37: Added `UnsafeNoOpPermissionResolver` warning-suppression note for unit-test fixtures.

## Revision Pass 2 (post p1429/p1430)

- G1: Completed `typed-harness.md` import topology DAG with all v2 modules (`harness/errors.py`, `harness/claude_preflight.py`, `harness/bundle.py`, `launch/constants.py`, `launch/context.py`, `launch/text_utils.py`, `projections/_guards.py`, `projections/_reserved_flags.py`) and explicit upward edges; linked from overview §5.
- G2: Added `typed-harness.md` §Bundle Registry with canonical `HarnessBundle[SpecT]`, `_REGISTRY`, and `get_harness_bundle(harness_id)` contract; referenced registry consumption from shared-core context assembly.
- G3: Pinned reserved-flag constants/strip helper to `projections/_reserved_flags.py`; updated `permission-pipeline.md` and `transport-projections.md` imports/policy examples to use the canonical path.
- G4: Set `launch/launch_types.py` as single home for `ResolvedLaunchSpec` base body and `continue_fork` validator; replaced duplicated base block in `launch-spec.md` with a direct reference.
- G5: Added `launch/text_utils.py` to module-layout sections and documented its shared responsibilities in `runner-shared-core.md` and `overview.md`.
- G6: Removed `PreflightResult.extra_cwd_overrides`; shared-core env merge now uses `plan.env_overrides`, runtime overrides, and `preflight.extra_env` only.
- G7: Removed `LaunchContext.permission_config` duplicate state; context consumers now read `ctx.perms.config`.
- G8: Reworked Codex streaming accounting to per-consumer accounted sets tied to concrete consumer functions/modules, with explicit aggregation and clarified `interactive` ownership in env-building consumer.
- G9: Inlined `agent_name` on `ClaudeLaunchSpec` and `OpenCodeLaunchSpec`; deleted `_AgentNameMixin` in design samples and updated D10 accordingly.
- G10: Simplified Codex streaming drift check by removing one-off `_SPEC_DELEGATED_FIELDS` indirection and validating with `delegated=frozenset()`.

## Revision Pass 3 (post p1433/p1434/p1435) — Reframe as Coordinator

Three independent audits converged on the same picture: rounds 1–2 combined genuine internal-consistency gaps with overreach into user and harness behavior. Round 3 separates the two. Meridian is a coordinator, not a policy engine. Every strict check answers "does this protect against meridian's own internal drift?" If not, it's deleted.

### Dropped — Overreach

- H1 (D1): **Deleted** all reserved-flag machinery. `_RESERVED_CODEX_ARGS`, `_RESERVED_CLAUDE_ARGS`, `strip_reserved_passthrough`, the `projections/_reserved_flags.py` module, any `strip` / heuristic / probe-derived inventories. `extra_args` is forwarded verbatim to every transport. Meridian is not the security gate for passthrough flags; the harness is. Users can invoke the harness directly with the same flags — meridian silently stripping them is worse than forwarding them.
- H2 (D2): **Rejected** adding a `@model_validator` that validates `PermissionConfig` combinations like `approval=confirm + sandbox=yolo`. If the harness accepts the combo, meridian accepts it. Meridian is not the authority on which combinations make semantic sense.
- H3 (D3): **Rejected** any `_FORBIDDEN_FIELD_PREFIXES = frozenset({"mcp_"})`-style import-time check on `SpawnParams` field names. Special-casing against a specific string prefix is hacky; the existing projection drift guard already catches "field with no consumer".

### Restored — Reversing round 2 overreach

- H4 (D4): **Restored** `mcp_tools: tuple[str, ...] = ()` as a first-class field on `ResolvedLaunchSpec` (reversing round 2 D23). Projections map it to Claude `--mcp-config`, Codex `-c mcp.servers.X.command=...`, and OpenCode HTTP session payload `mcp` field. Auto-packaging through mars is still out of scope for v2; manual `mcp_tools` configuration works today. The projection drift guards count it as a normal field with no special handling.
- H5 (D5): **Retained** `PermissionConfig` Literals for now, with a documented friction-free extension path: adding a new sandbox tier or approval mode is a one-line edit to the tuple plus per-harness projection mapping updates. No runtime probing, no `--help` parsing, no auto-detection. Literals are developer-facing documentation and type-checker support, not a runtime gate.

### Kept — Real internal-consistency invariants

- K1 (H6): Bundle dispatch is keyed on `(harness_id, transport_id)`. `HarnessBundle[SpecT]` carries a `connections: Mapping[TransportId, type[HarnessConnection[SpecT]]]` mapping. Adding Claude-over-HTTP in the future is a one-line bundle addition, not a rewiring of dispatch. `typed-harness.md §Dispatch Boundary` is updated; a new `TransportId` enum lives next to `HarnessId`.
- K2 (H7): Bundle registration goes through a single `register_harness_bundle(bundle)` helper that raises `ValueError` on duplicate `harness_id`. `harness/__init__.py` imports every concrete adapter module eagerly so registration happens before the first dispatch. Unit test S039 asserts duplicate registration fails.
- K3 (H8): `BaseSubprocessHarness.id` is `@abstractmethod`, reconciling the `HarnessAdapter` Protocol method set against the ABC abstract-method set. A subclass that forgets `id` now fails at instantiation with `TypeError` instead of crashing deep in dispatch with `AttributeError`. Unit test S040 cross-checks Protocol attributes vs ABC abstractmethods.
- K4 (H9): `PermissionResolver.resolve_flags()` no longer takes a `harness` parameter. The old signature `resolve_flags(self, harness: HarnessId)` invited `if harness == CLAUDE` branching inside the resolver, re-introducing the harness-id dispatch `adapter.preflight()` was meant to eliminate. New shape: resolvers expose intent via `config`; projections translate per harness. Chose option (a) from the brief (drop the parameter entirely) because it cleanly forbids harness branching rather than relying on documented restraint.
- K5 (H10): `RuntimeContext.child_context()` is the sole producer of `MERIDIAN_*` runtime overrides. `merge_env_overrides(...)` enforces the invariant: if `preflight.extra_env` contains any `MERIDIAN_*` key it raises `RuntimeError`. Scenario S046 exercises this.
- K6 (H11): Pulled session-id extraction parity into v2 scope. Added `HarnessExtractor[SpecT]` to `HarnessBundle`. Subprocess and streaming both call `bundle.extractor.detect_session_id_from_artifacts(...)` for fallback detection from harness-specific artifacts (Claude project files, Codex rollout files, OpenCode logs). Closes the p1385 gap that streaming had no fallback session detection. Chose pull-in over explicit deferral because the design absorbed it without blowing scope.
- K7 (H12): `PermissionConfig` is now `model_config = ConfigDict(frozen=True)`. `PreflightResult.extra_env` is wrapped in `MappingProxyType` at construction. `LaunchContext.env` / `env_overrides` are wrapped in `MappingProxyType`. This is about internal-state integrity (meridian's own coordination depends on stable values during merge + projection), not about validating values.
- K8 (H13): Added explicit cancel/interrupt/SIGTERM semantics table to `typed-harness.md §Connection Contract`. `send_cancel` and `send_interrupt` are idempotent and converge to a single terminal spawn status. Runner signal handling is transport-neutral — SIGTERM/SIGINT translate into exactly one `send_cancel()` per active connection. Cancellation event emission is exactly-once per spawn, ordered before any subsequent error emission. Scenarios S041 (cancel idempotency), S042 (SIGTERM subprocess/streaming parity), S048 (race: cancel vs completion terminal status).
- K9 (H14): Added per-adapter `handled_fields: frozenset[str]` declaration. `harness/launch_spec.py` aggregates the union across registered bundles and asserts it equals `SpawnParams.model_fields` at import time. A new `SpawnParams` field that slips past the global `_SPEC_HANDLED_FIELDS` check but isn't claimed by any adapter now fails at import. Scenario S044.

### Clarifications

- H15 (C1): `LaunchContext` parity claim narrowed to the deterministic subset — `run_params`, `spec`, `child_cwd`, `env_overrides`. The `env` field as a whole depends on ambient `os.environ` and is explicitly NOT in the parity contract. S024 updated to assert parity on the deterministic subset only.
- H16 (C2): Added eager-import note to `transport-projections.md §Eager Import Bootstrapping`. `harness/__init__.py` imports every projection module so drift guards always execute at package load, not after the first dispatch.
- H17 (C3): Added soft line-budget marker to `transport-projections.md §Codex Streaming Projection`. If `project_codex_streaming.py` exceeds 400 lines, split into `project_codex_streaming_appserver.py` + `project_codex_streaming_rpc.py`. Follow D19 precedent.

### Retired scenarios

- S037 (reserved-flag stripping) is **retired** and replaced by S045 ("extra_args forwarded verbatim"). E37 is removed from `edge-cases.md`. E48 is the new verbatim-passthrough edge case.
- S023 (allowed-tools merged from resolver + extra_args) is **updated** to reflect verbatim forwarding: both flags appear, no merge, no strip.
- S011 / S012 are **retained but scoped** to resolver-internal dedupe only (multi-source merge inside the resolver), not dedupe against user `extra_args`.

### New scenarios

- S039 — Duplicate bundle registration raises `ValueError`.
- S040 — Protocol/ABC method-set reconciliation test.
- S041 — `send_cancel` idempotency.
- S042 — SIGTERM parity across subprocess and streaming.
- S043 — Missing extractor in bundle fails at registration.
- S044 — New `SpawnParams` field without an adapter owner fails at import time.
- S045 — `extra_args` forwarded verbatim to every transport (replaces S037).
- S046 — `preflight.extra_env` containing `MERIDIAN_*` raises in `merge_env_overrides`.
- S047 — `mcp_tools` projects to every harness's wire format.
- S048 — Cancel vs completion race: exactly-one terminal status persisted.
- S049 — Streaming session-id fallback via `HarnessExtractor`.
- S050 — `(harness, transport)` dispatch for unsupported transport raises `KeyError`.
- S051 — `PermissionConfig` frozen: mutation raises.
