# Workspace Config Architecture Overview

## Summary

The architecture splits project-root file policy from `.meridian/` runtime state, keeps project settings and workspace topology in separate root-level files, and routes both through shared read models so config commands, spawn paths, and diagnostics observe the same state. This tree is observational: it describes the target shape and the constraints implementation must preserve.

Terminology: **project root** names the parent directory of the active `.meridian/`. It is an internal concept; user-facing spec leaves describe files by relationship to `.meridian/` rather than naming an anchor. See `decisions.md` D12.

## TOC

- **A01** — [paths-layer.md](paths-layer.md): new project-root file abstraction and its boundary with `StatePaths`.
- **A02** — [config-loader.md](config-loader.md): project-config state machine (`absent | present`), read/write resolution, and command-family consistency.
- **A03** — [workspace-model.md](workspace-model.md): parsed workspace representation, validation tiers, and forward-compatible unknown-key handling.
- **A04** — [harness-integration.md](harness-integration.md): harness-owned `HarnessWorkspaceProjection`, fixed launch ordering, and per-harness mechanism mapping for Claude, Codex, and OpenCode.
- **A05** — [surfacing-layer.md](surfacing-layer.md): `config show`, `doctor`, and launch-diagnostic shapes.

## Cross-Cutting Decisions

- **Boundary split.** Project-root policy files move behind a new `ProjectPaths` layer so `StatePaths` stays `.meridian`-scoped (`probe-evidence/probes.md:139-145`).
- **One state snapshot, many consumers.** Loader logic, config commands, `doctor`, and harness launch paths should consume the same observed config/workspace state instead of partially re-deriving it in each command family (`probe-evidence/probes.md:60-100`).
- **Structured internal workspace roots.** The user-facing TOML stays minimal, but the internal model carries ordering and provenance so injection, diagnostics, and future growth do not depend on a lossy `list[Path]` abstraction (`probe-evidence/probes.md:20-47` and `prior-round-feedback.md:17-21`).
- **Projection interface, not mechanism branches.** Launch code computes ordered roots once, then adapters translate them into `HarnessWorkspaceProjection` objects. This keeps workspace-config policy out of harness-specific mechanisms and lets OpenCode use config-overlay transport without infecting Claude/Codex paths.

## Reading Order

Read `paths-layer.md` first because the file-ownership boundary drives every other leaf. Then read `config-loader.md` and `workspace-model.md` for the two read models, `harness-integration.md` for launch behavior, and `surfacing-layer.md` for user-visible state.
