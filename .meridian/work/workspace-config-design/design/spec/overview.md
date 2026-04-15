# Workspace Config Spec Overview

## Purpose

This spec tree defines the behavioral contract for workspace-config. The design is boundary-first: committed project policy lives in the same directory as the active `.meridian/`, local workspace topology lives in a local-only file beside that `.meridian/`, and `.meridian/` itself remains runtime/local state. The overview is a strict TOC; substantive EARS requirements live in the leaf files.

## TOC

- **CFG-1** — Project config location ([config-location.md](config-location.md)): `meridian.toml` in the same directory as the active `.meridian/` as the canonical committed project config, and no precedence regressions.
- **WS-1** — Workspace topology file ([workspace-file.md](workspace-file.md)): `workspace.local.toml` naming, discovery order, minimal schema, unknown-key preservation, and init behavior.
- **CTX-1** — Context-root injection ([context-root-injection.md](context-root-injection.md)): how enabled roots become harness arguments, ordering relative to user passthrough and inherited roots, and v1 harness support boundaries.
- **SURF-1** — State surfacing ([surfacing.md](surfacing.md)): how `config show`, `doctor`, and launch-time diagnostics report workspace/config state without hiding errors or spamming users.
- **BOOT-1** — Bootstrap and opt-in file creation ([bootstrap.md](bootstrap.md)): what first-run creates automatically, what remains opt-in, and how `config init` creates root config on request.

## Reading Order

Read `config-location.md` first because it defines the root-vs-state boundary. Then read `workspace-file.md` for the local topology file itself, `context-root-injection.md` for launch behavior, `surfacing.md` for diagnostics, and `bootstrap.md` for creation entrypoints.
