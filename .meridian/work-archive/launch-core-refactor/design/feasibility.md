# Feasibility Record

Probe evidence and assumption verdicts for the launch-core refactor. This document grounds design decisions in runtime reality.

## Verdicts

### FV-11 Raw-`SpawnRequest` factory boundary is viable

**Verdict**: feasible. The factory can accept a fully raw `SpawnRequest`
(prompt, model ref, harness id, agent ref, skills refs, sandbox/approval/
allowed/disallowed tools, extra_args, mcp_tools, retry policy, raw session
intent) and produce a complete `LaunchContext` without driver-side
pre-resolution. The persisted prepare→execute artifact reduces to a serialized
`SpawnRequest`; the resolver and resolved permission config are reconstructed
by the factory at execute time.

**Evidence**: code probe of current behavior shows resolver is *already*
constructed twice today — once in `lib/ops/spawn/prepare.py:323` to seed the
preview command and store the persisted plan, and again in
`lib/ops/spawn/execute.py:861` for the live launch. The current resolver
object stored on `PreparedSpawnPlan.execution.permission_resolver` is not
load-bearing across the boundary; only the raw inputs survive serialization
in any meaningful way (the persisted `PermissionConfig` is a frozen pydantic
DTO with no live mutable state). Removing the persisted resolver and
reconstructing in the factory is a behavior-preserving consolidation.

**Evidence**: `lib/launch/context.py:175-203` — the current factory body
already reads `plan.execution.permission_resolver` and
`plan.execution.permission_config` *without* mutating them. They function as
opaque pass-throughs from the driver. The raw-input redesign is the same
data flow inverted: instead of driver → factory passing pre-resolved objects,
factory consumes raw fields and produces them locally. No new reachability
or lifetime constraint emerges.

**Evidence**: `lib/harness/adapter.py:150-163` — `SpawnRequest` already
exists on the harness adapter protocol but is unused. Making it load-bearing
removes the dead-abstraction signal and sidesteps the naming churn of
introducing yet another DTO.

**Residual risk**: per-driver constructions of `SpawnRequest` will need to
populate every raw field today's drivers compute incidentally (e.g. profile
name from `--agent` resolution). The structural review already enumerated
the construction sites (`launch/plan.py:178-213`,
`ops/spawn/prepare.py:356-397`, `app/server.py:332-350`,
`cli/streaming_serve.py:69-87`, `ops/spawn/execute.py:397-425`); R06 collapses
each to a single `SpawnRequest(...)` call followed by `build_launch_context()`.
No driver computes inputs the factory cannot reconstruct from raw fields.

**Residual risk**: the worker prepare→execute serialization needs round-trip
fidelity. `SpawnRequest` is a frozen pydantic model with primitive-typed
fields; pydantic's `model_dump_json` / `model_validate_json` cover this with
no `arbitrary_types_allowed=True` escape hatch (the current
`PreparedSpawnPlan` requires this hatch to carry the live `PermissionResolver`).
Removing the live resolver from the persisted artifact is a strict simplification.

### FV-12 Reviewer-as-drift-gate fits the CI loop

**Verdict**: feasible. The agent-staffing skill documents reviewer-as-CI
architectural drift gate as an established pattern for surfaces where
declared invariants are too semantic for grep checks. Meridian itself has the
spawn machinery to invoke it from CI (`meridian spawn -a reviewer`).

**Evidence**: `agent-staffing` skill resource section "@reviewer as
Architectural Drift Gate" describes the exact pattern. The skill recommends
pairing with deterministic behavioral tests as backstop, which matches R06's
verification design.

**Residual risk**: reviewer judgments are probabilistic. R06 mitigates this
by (a) pinning the highest-leverage invariants as deterministic factory
tests, and (b) using a cheaper model variant for the routine drift check
(`meridian models list` → use a `mini`/`flash` family for routine PRs;
escalate to default reviewer model on PRs that touch the protected surface
heavily). The invariant prompt at
`.meridian/invariants/launch-composition-invariant.md` is version-controlled
and updated alongside legitimate architecture changes.

**Residual risk**: CI cost. R06 sets the drift gate to spawn only on PRs
touching files under `src/meridian/lib/(launch|harness|ops/spawn|app)/` so
typical PRs do not pay the cost.

## How this file was produced

Verdicts extracted from the workspace-config-design feasibility record, covering the R06-relevant FV-11 and FV-12 entries. The full original probes.md capture is in the workspace-config-design work directory.
