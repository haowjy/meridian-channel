# Requirements: Storage, Config, and Workspace Boundaries

## Problem Statement

Meridian and Mars are intertwined products sharing a repo. Their on-disk state model has unclear boundaries:

1. **Committed config lives in the wrong place.** `config.toml` sits inside `.meridian/` — a mostly-gitignored state root — tracked only via a gitignore exception. It should live at the repo root alongside `mars.toml`, where committed project policy belongs.

2. **`.meridian/` conflates three roles.** It currently holds committed shared artifacts (`config.toml`, `fs/`, `work/`), local runtime state (`spawns.jsonl`, `sessions.jsonl`), and transient artifacts (`spawns/`, `cache/`). The gitignore-with-exceptions pattern makes it unclear what is committed vs local, and it obscures the intended end-state where `.meridian/` becomes entirely local/runtime state.

3. **Mars has no local state directory.** Mars generates `.agents/` output but has no `.mars/` for its own runtime state (e.g., sync cache, integrity state). Its local state concerns shouldn't live in `.meridian/`.

4. **AGENTS.md hardcodes personal filesystem paths.** References like `~/gitrepos/prompts/meridian-base` are non-portable across developers.

5. **No centralized multi-root injection.** Developers working across multiple repos manually configure each harness's directory-inclusion mechanism. There is no single place to declare "these repos participate in my dev environment" and have Meridian inject them into all harnesses.

## What the Prior Design Got Wrong

The previous workspace-config design over-centered `workspace.toml` as the primary problem. The real issue is **boundary clarity**: what belongs at repo root vs `.meridian/` vs `.mars/`, what is committed vs local-only vs runtime, and how workspace/context-root injection fits into that broader picture. The workspace file is one piece of the solution, not the framing.

## Reframed Goals

### G1: State Ownership Clarity
Every file on disk belongs to exactly one owner with clear committed/local/runtime classification. A developer or agent should know, without consulting documentation, whether a given file is committed, local-only, or transient runtime state.

### G2: Committed Project Config at Repo Root
Shared, committed project policy lives at the repo root in named config files (e.g., `meridian.toml`), not inside state directories with gitignore exceptions.

### G3: Mars Conceptual Separability
Mars remains conceptually separable from Meridian. Mars-owned state and config do not live under `.meridian/`. Meridian-owned state and config do not live under `.mars/`.

### G4: Canonical Repo References
AGENTS.md and committed config reference repos by canonical identity (`org/repo`), not personal filesystem paths.

### G5: Centralized Context-Root Injection
A local-only workspace file lets developers declare extra roots once and have Meridian inject them into harness launches. Default behavior: all declared roots apply to all harnesses. Per-harness overrides are possible but not required.

### G6: Settings/Config Separate from Workspace/Topology
Operational settings (model, harness, approval, etc.) and workspace topology (which repos, which roots) are distinct concerns in distinct files. The workspace file is not a junk drawer for runtime settings.

### G7: `.meridian/` Trends Fully Local
The design SHALL treat `.meridian/` as a directory that trends toward fully local/runtime state and fully gitignored over time. Any committed paths that remain under `.meridian/` are transitional exceptions, not the target model.

### G8: Future Cloud Evolution Not Trapped
The design must not create dependencies that block future migration of work/fs artifacts to cloud/shared state. Git-tracked `fs/`, `work/`, and `work-archive/` are temporary compatibility choices until a shared/cloud alternative exists.

## Constraints

- Must not break existing config precedence (CLI > ENV > profile > project > user > harness default).
- Incremental migration is superseded by D8 (2026-04-14). Old `.meridian/config.toml` does not continue to work during transition because no transition exists in this redesign; see `.meridian/work/workspace-config-design/decisions.md` D8.
- Must be local-only (gitignored) for workspace topology — no developer's filesystem layout leaks into committed files.
- Must not require mars-agents changes in the first version.
- Normal users who don't work across repos experience no new complexity.
- Must treat committed `.meridian/fs/`, `.meridian/work/`, and `.meridian/work-archive/` as transitional exceptions to the long-term `.meridian/` contract, not as precedent for adding more committed config there.

## Scope Boundaries

- **Deferred — Mars local state directory.** Problem Statement item 3 ("Mars has no local state directory") is not addressed in this work item. `workspace.local.toml` and `meridian.toml` clarify Meridian-side boundaries only; any `.mars/` or Mars-runtime-state design belongs to a separate Mars-scoped work item.
- **Deferred — AGENTS.md copy cleanup.** Problem Statement item 4 ("AGENTS.md hardcodes personal filesystem paths") is not addressed in this work item. The workspace file solves the topology declaration problem, but the documentation copy edit to remove personal paths from `AGENTS.md` is separate follow-up work.

## Non-Goals (First Version)

- Cloud-backed work/fs artifacts.
- Shareable team workspace config.
- Workspace-level model or harness overrides.
- Auto-detection of local repo checkouts.
- Per-harness context-root subsets (declare once, all harnesses get all roots).
- Replacing mars.local.toml (workspace config bridges to it, does not replace it).
- Moving `fs/`, `work/`, or `work-archive/` out of `.meridian/` in the first version (acknowledged as future migration, not this version).
