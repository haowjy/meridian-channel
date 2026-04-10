# Edge Cases, Failure Modes, Boundary Conditions

## Purpose

Authoritative edge-case set for v2. Each item maps to `scenarios/Sxxx-*.md` and must be verified before completion.

## Category A — Type and Contract Boundaries

### E1 — Adapter omits `resolve_launch_spec`

Expected: pyright structural failure + runtime `TypeError` from ABC abstract-method enforcement (`BaseSubprocessHarness`), not from Protocol instantiation.

### E2 — Base spec passed to concrete connection

Expected: pyright type error and runtime `TypeError` at dispatch boundary (`isinstance(spec, bundle.spec_cls)` guard in `SpawnManager.start_spawn`), not in per-connection behavior-switching branches.

### E3 — `None` permission resolver

Expected: type error; no cast-to-None path.

### E4 — Resolver lacks `.config`

Expected: Protocol conformance/type-check failure.

### E5 — New `ClaudeLaunchSpec` field missed by projection

Expected: import-time `ImportError` via `_check_projection_drift`.

### E6 — New `SpawnParams` field missed by factory accounting

Expected: import-time `ImportError` from `_SPEC_HANDLED_FIELDS` accounting.

## Category B — Permission Flow

### E7 — Streaming Codex with `sandbox=read-only`

Expected: app-server launch projects read-only sandbox semantics; write attempts rejected.

### E8 — Streaming Codex with `approval=auto`

Expected: semantic auto-accept behavior and audit trace.

### E9 — Streaming Codex with `approval=default`

Expected: no forced override; harness default preserved.

### E10 — Streaming Codex with `approval=confirm`

Expected: rejection event enqueued before `send_error` is awaited.

### E11 — Streaming Claude `--allowedTools` dedupe

Expected: one deduped merged `--allowedTools` emission.

### E12 — Subprocess Claude parity with E11

Expected: same deduped semantics.

### E13 — REST `/spawns` missing permission metadata

Expected: strict default rejects request (`HTTP 400`). Only if `--allow-unsafe-no-permissions` is enabled may `UnsafeNoOpPermissionResolver` be used.

### E14 — `run_streaming_spawn` caller-provided resolver

Expected: caller resolver flows through unchanged.

## Category C — Spec-to-Wire Completeness and Projection Semantics

### E15 — Claude full-field round-trip

Expected: canonical order and field-by-field wire mapping table coverage.

### E16 — Codex sandbox x approval matrix

Expected: distinct semantic behavior + audit trail per cell. Wire strings may collapse where harness supports fewer distinct knobs.

### E17 — OpenCode model prefix normalization

Expected: one-time normalization.

### E18 — OpenCode skills single-injection

Expected: exactly one authoritative skills channel.

### E19 — Codex `report_output_path`

Expected: subprocess emits `-o`; streaming ignores wire emission and logs debug note.

### E20 — `continue_fork=True` without session ID

Expected: base-spec validator failure for all harness subclasses.

## Category D — Arg Ordering and Override Policy

### E21 — Claude subprocess/streaming arg-tail parity

Expected: same projected tail for same spec.

### E22 — User `--append-system-prompt` in passthrough

Expected: both flags appear; user tail value wins by last-wins semantics; warning emitted.

### E23 — `--allowedTools` resolver + passthrough merge

Expected: one merged deduped flag.

## Category E — Shared Core and Structure

### E24 — `LaunchContext` parity

Expected: identical context from identical inputs.

### E25 — Parent Claude permissions forwarding

Expected: identical preflight semantics across runners via adapter preflight.

### E26 — Shared constants only

Expected: no duplicate constants in runner files.

## Category F — Environment and Runtime Failures

### E27 — `python -O` behavior

Expected: guard behavior unchanged (no assert-based enforcement).

### E28 — Missing harness binary

Expected: shared structured `HarnessBinaryNotFound` error semantics across runners.

### E29 — Invalid Codex passthrough args

Expected: debug log before launch and clean surfaced failure.

## Category G — Import Order / Guard Coverage

### E30 — Projection guard import-time behavior

Expected: `project_*` modules fail at import on drift.

### E31 — No circular imports

Expected: DAG centered on `launch_types.py` remains acyclic.

### E36 — Delegated field has no consumer

Expected: transport-wide accounted-field union check fails import when any delegated field is unconsumed.

## Category H — Observability

### E32 — Confirm-mode rejection event ordering

Expected: enqueue-before-send ordering assertion uses call sequence/sequence id, not wall-clock.

### E33 — Passthrough debug log on streaming

Expected: Codex in `project_codex_spec_to_appserver_command`; OpenCode in `project_opencode_spec_to_serve_command`.

### E37 — Reserved-flag stripping

Expected: reserved permission passthrough flags are stripped/merged with warning logs; effective policy unchanged.

### E38 — Codex fail-closed capability mismatch

Expected: if requested sandbox/approval cannot be represented by app-server interface, raise `HarnessCapabilityMismatch` and fail spawn before launch.

## Category I — Connection Surface

### E34 — `OpenCodeConnection` inherits `HarnessConnection`

Expected: inheritance enforced.

### E35 — Unified connection interface

Expected: all concrete connections satisfy same `HarnessConnection` ABC surface.
