# Workspace Config Architecture Overview

## Summary

The architecture splits project-root file policy from `.meridian/` runtime state, keeps project settings and workspace topology in separate root-level files, and routes both through shared read models so config commands, spawn paths, and diagnostics observe the same state. A06 covers the launch-domain core that A04's workspace projection plugs into: composition is consolidated into one factory and one typed pipeline, with three driving adapters and three driven adapters bracketing it. This tree is observational: it describes the target shape and the constraints implementation must preserve.

Terminology: **project root** names the parent directory of the active `.meridian/`. It is an internal concept; user-facing spec leaves describe files by relationship to `.meridian/` rather than naming an anchor. See `decisions.md` D12.

## TOC

- **A01** — [paths-layer.md](paths-layer.md): new project-root file abstraction and its boundary with `StatePaths`.
- **A02** — [config-loader.md](config-loader.md): project-config state machine (`absent | present`), read/write resolution, and command-family consistency.
- **A03** — [workspace-model.md](workspace-model.md): parsed workspace representation, validation tiers, and forward-compatible unknown-key handling.
- **A04** — [harness-integration.md](harness-integration.md): harness-owned `HarnessWorkspaceProjection`, fixed launch ordering, and per-harness mechanism mapping for Claude, Codex, and OpenCode.
- **A05** — [surfacing-layer.md](surfacing-layer.md): `config show`, `doctor`, and launch-diagnostic shapes.
- **A06** — [launch-core.md](launch-core.md): launch-domain core — typed pipeline owned by `build_launch_context()`, raw `SpawnRequest` boundary, single-owner constraints, fork transaction ordering, and the verification triad replacing `scripts/check-launch-invariants.sh`.

## Cross-Cutting Decisions

- **Boundary split.** Project-root policy files move behind a new `ProjectPaths` layer so `StatePaths` stays `.meridian`-scoped (`probe-evidence/probes.md:139-145`).
- **One state snapshot, many consumers.** Loader logic, config commands, `doctor`, and harness launch paths should consume the same observed config/workspace state instead of partially re-deriving it in each command family (`probe-evidence/probes.md:60-100`).
- **Structured internal workspace roots.** The user-facing TOML stays minimal, but the internal model carries ordering and provenance so injection, diagnostics, and future growth do not depend on a lossy `list[Path]` abstraction (`probe-evidence/probes.md:20-47` and `prior-round-feedback.md:17-21`).
- **Projection interface, not mechanism branches.** Launch code computes ordered roots once, then adapters translate them into `HarnessWorkspaceProjection` objects. This keeps workspace-config policy out of harness-specific mechanisms and lets OpenCode use config-overlay transport without infecting Claude/Codex paths.
- **One factory, one pipeline.** Launch composition lives only inside `build_launch_context()` and its named pipeline stages. Driving adapters construct a raw `SpawnRequest` and hand it to the factory; they never call `resolve_policies`, `resolve_permission_pipeline`, `adapter.resolve_launch_spec`, `adapter.build_command`, or `adapter.fork_session` directly. This is what makes A04 honest — there is exactly one place where workspace projection plugs in (`decisions.md` D17 and D19; `feasibility.md` FV-11 and FV-12).

## Reading Order

Read `paths-layer.md` first because the file-ownership boundary drives every other leaf. Then read `config-loader.md` and `workspace-model.md` for the two read models, `harness-integration.md` for launch behavior, `launch-core.md` for the launch-domain structure that hosts the harness-integration seam, and `surfacing-layer.md` for user-visible state.
