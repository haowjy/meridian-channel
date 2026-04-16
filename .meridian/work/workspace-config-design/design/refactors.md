# Workspace Config Refactor Agenda

This agenda covers structural rearrangements the planner must account for before or alongside feature work. Scope entries cite the live probe evidence so implementation phases can anchor their file lists to observed code, not memory.

**Dependency graph:** R01 → R02 (prep before rewire). R03 is follow-up only (conditional on post-implementation drift). R04 is folded into R01.

**External dependencies:** This work item depends on the **launch-core-refactor** work item completing first. The workspace projection pipeline stage (`apply_workspace_projection()`) plugs into the launch domain core. The harness-agnostic workspace-projection interface and the launch composition refactor are separate work items in **launch-core-refactor**.

## R01 — Separate project-root file policy from `StatePaths`

Includes former R04 scope.

- **Type:** prep refactor
- **Why:** `StatePaths` is `.meridian`-scoped today. Adding `meridian.toml` or `workspace.local.toml` logic there would mix project-root policy with local runtime state (`probe-evidence/probes.md:139-145`).
- **Scope:**
  - `src/meridian/lib/config/project_paths.py` — **new module**, owns `ProjectPaths` definition. This is the primary output of R01: a cohesive abstraction for project-root file policy separate from `StatePaths`.
  - `src/meridian/lib/state/paths.py:21,33,127` — current `.meridian/config.toml` and `.meridian/.gitignore` policy live here (`probe-evidence/probes.md:68-72`).
  - `src/meridian/lib/config/settings.py:206-210` — project-config resolver currently depends on `StatePaths.config_path` (`probe-evidence/probes.md:72-74`).
  - `src/meridian/lib/config/settings.py:789-823` — project-root detection exists today as `resolve_repo_root`; R01 renames this to `resolve_project_root` and models root-level files as a cohesive layer (`probe-evidence/probes.md:143-145`).
  - Rename caller set from live probe (`rg -n "resolve_repo_root" src/ tests/`):
    `src/meridian/lib/catalog/models.py:30,40,299`,
    `src/meridian/lib/catalog/skill.py:8,97,143`,
    `src/meridian/lib/catalog/agent.py:10,168,209`,
    `src/meridian/lib/launch/plan.py:10,159`,
    `src/meridian/cli/main.py:1317,1320`,
    `src/meridian/lib/ops/runtime.py:12,63`,
    `src/meridian/lib/ops/catalog.py:21,189`,
    `src/meridian/lib/ops/config.py:16,346,348,776,826,845,871`,
    and `src/meridian/lib/config/settings.py:802`.
- **Exit criteria:**
  - A new project-root file abstraction (`ProjectPaths`) owns `meridian.toml` and `workspace.local.toml`.
  - `StatePaths` no longer owns the canonical project-config path.
  - Project-root file policy can evolve without expanding the `.meridian` path object.
  - `resolve_repo_root` is renamed to `resolve_project_root` so the internal name matches the concept. No user-facing "repo root" term remains in spec leaves or CLI copy.
  - The `.meridian/.gitignore` `!config.toml` exception is removed as part of this refactor (see R04 below — folded here).

## R02 — Rewire the config command family end-to-end

- **Type:** prep refactor
- **Why:** Moving project config is not a resolver tweak. Loader, config commands, runtime bootstrap, CLI copy, and tests all currently point at `.meridian/config.toml` or `_config_path()` (`probe-evidence/probes.md:60-100`).
- **Scope:**
  - `src/meridian/lib/config/settings.py:206-227` — loader project/user config resolution (`probe-evidence/probes.md:72-74`).
  - `src/meridian/lib/ops/config.py:342-343,602-606,737-763,758,777,827,846,872` — config-path helper, bootstrap, and every config subcommand (`probe-evidence/probes.md:75-79`, `probe-evidence/probes.md:151-158`).
  - `src/meridian/lib/ops/runtime.py:66` — startup path that triggers bootstrap (`probe-evidence/probes.md:151-158`).
  - `src/meridian/lib/ops/manifest.py:242,266` and `src/meridian/cli/main.py:806-815` — user-facing command descriptions (`probe-evidence/probes.md:80-87`).
  - Live test/smoke hits from `rg -l "config\\.toml|_config_path" tests/`:
    `tests/smoke/config/init-show-set.md`,
    `tests/smoke/quick-sanity.md`.
- **Exit criteria:**
  - One `ProjectConfigState` (with states `absent | present`) is shared by the settings loader, config commands, bootstrap, and diagnostics.
  - All project-config reads and writes target `meridian.toml` through the shared `ProjectConfigState`; no command resolves project config from a different location.
  - Generic bootstrap (`ensure_state_bootstrap_sync`) no longer auto-creates project-root config; it creates only `.meridian/` runtime directories and `.meridian/.gitignore`.
  - CLI help, manifests, and tests all describe `meridian.toml` as the canonical project config.
  - `config migrate` does not exist; no legacy fallback code paths are introduced.

## R03 — Keep direct `--add-dir` emitters narrow after workspace projection lands

- **Type:** follow-up only if post-workspace-projection duplication remains
- **Why:** The workspace projection interface (delivered by launch-core-refactor) moves ordering/applicability into a harness-agnostic projection interface. A separate shared `--add-dir` emitter is only justified if the remaining Claude/Codex direct-flag materialization starts drifting after that.
- **Scope:**
  - `src/meridian/lib/harness/projections/project_claude.py` — final Claude CLI token emission.
  - `src/meridian/lib/harness/projections/project_codex_subprocess.py:189-227` — final Codex CLI token emission (`probe-evidence/probes.md:106-123`).
  - `src/meridian/lib/launch/text_utils.py:8-19` — first-seen dedupe semantics remain shared and load-bearing (`probe-evidence/probes.md:24-38`).
- **Exit criteria:**
  - If this follow-up is needed at all, it factors only direct `--add-dir` token emission.
  - Ordering, applicability, diagnostics, and OpenCode overlay handling remain owned by the workspace projection interface, not by a new generic flag builder.

## R04 — Remove the `.meridian/.gitignore` `!config.toml` exception

- **Type:** folded into R01
- **Why:** The `.meridian/.gitignore` `!config.toml` exception is legacy scaffolding from when `.meridian/config.toml` was committed. With no migration and no legacy fallback, removing it is unconditional and belongs alongside R01.
- **Scope:**
  - `src/meridian/lib/state/paths.py:21,33` — `_GITIGNORE_CONTENT` and `_REQUIRED_GITIGNORE_LINES` currently preserve the exception (`probe-evidence/probes.md:70-71`).
- **Exit criteria:** folded into R01's exit criteria above. Normal runtime bootstrap does not preserve `.meridian/config.toml` as a committed exception.
