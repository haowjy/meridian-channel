# A01: Paths Layer

## Summary

The current codebase has `StatePaths` for `.meridian/` files and no equivalent abstraction for project-root policy files. The target shape adds a separate project-root file layer and keeps `StatePaths` focused on local/runtime state only.

Terminology: **project root** names the parent directory of the active `.meridian/`. It is an internal concept and does not appear in user-facing spec leaves; user-facing docs describe files by relationship to `.meridian/`. See `decisions.md` D12.

## Realizes

- `../spec/config-location.md` — `CFG-1.u1`, `CFG-1.u3`
- `../spec/workspace-file.md` — `WS-1.u1`, `WS-1.u2`
- `../spec/bootstrap.md` — `BOOT-1.u1`, `BOOT-1.e2`

## Current State

- `StatePaths` is `.meridian`-scoped today: it exposes `root_dir`, `spawns_dir`, `cache_dir`, and `config_path = root_dir / "config.toml"` (`probe-evidence/probes.md:64-71`, `probe-evidence/probes.md:139-145`).
- There is no first-class project-root file abstraction. `resolve_repo_root()` at `lib/config/settings.py:804-838` locates the directory but project-root-level config/workspace files are not modeled as a cohesive layer (`probe-evidence/probes.md:139-145`). Target state renames this to `resolve_project_root` so the internal name matches the concept.
- `.meridian/.gitignore` currently has a committed exception for `config.toml`, which is a symptom of the wrong boundary rather than a durable contract (`probe-evidence/probes.md:70-71`).

## Target State

Introduce a separate project-root file abstraction, referred to here as `ProjectPaths`, with responsibility for:

- locating `meridian.toml`
- locating `workspace.local.toml`
- resolving `MERIDIAN_WORKSPACE`
- exposing project-local ignore policy for `workspace.local.toml`

`StatePaths` remains responsible only for `.meridian/` runtime and cache files.

### Proposed shape

```text
ProjectPaths
  project_root
  meridian_toml
  workspace_local_toml
  workspace_override_env
  workspace_ignore_target

StatePaths
  root_dir (.meridian)
  spawns_dir
  artifacts_dir
  cache_dir
  sessions_path
  spawns_path
  ...
```

### Discovery rules

- **Project config**: canonical path is `<project-root>/meridian.toml`. If absent, no project config is in effect.
- **Workspace file**: if `MERIDIAN_WORKSPACE` is set to an absolute path, that path wins; otherwise use `<project-root>/workspace.local.toml`.
- **`MERIDIAN_WORKSPACE` path semantics (v1)**: absolute paths only. Relative-path resolution is deferred per D12 until a concrete user need surfaces.
- **Paths inside `workspace.local.toml`**: resolved relative to the file itself (VS Code `.code-workspace` convention), so the file remains portable across moves.

### Ownership boundary

| Concern | Owner |
|---|---|
| `.meridian/` directories, pid files, JSONL state, `.meridian/.gitignore` | `StatePaths` |
| `meridian.toml`, `workspace.local.toml`, workspace override env, file location resolution | `ProjectPaths` |
| `workspace.local.toml` loading, parsing, schema validation, snapshot construction | `config/workspace.py` + `workspace_snapshot.py` |

## Module Layout

New modules introduced by this design:

| Module | Ownership |
|---|---|
| `src/meridian/lib/config/project_paths.py` | Project-root Meridian file policy. Defines `ProjectPaths` and resolves the file locations for `meridian.toml`, `workspace.local.toml`, and `MERIDIAN_WORKSPACE` without touching state-root concerns. |
| `src/meridian/lib/config/project_config_state.py` | Canonical project-config state machine (`absent | present`). Shared by loader and mutation commands so read/write behavior cannot diverge. |
| `src/meridian/lib/config/workspace.py` | `workspace.local.toml` loading, parsing, schema validation, unknown-key preservation, and `WorkspaceConfig` document model after `ProjectPaths` chooses which file to consult. |
| `src/meridian/lib/config/workspace_snapshot.py` | Filesystem evaluation and diagnostic shaping: missing roots, enabled counts, invalid-file findings, and per-harness applicability matrix. Produces `WorkspaceSnapshot`. |
| `src/meridian/lib/launch/context_roots.py` | Shared launch-time ordered-root planner. Chooses which enabled existing roots participate in a launch and in what order; harness adapters translate that plan into tokens or overlays. |
| `src/meridian/lib/ops/workspace.py` | New `meridian workspace` command family, starting with `workspace init`. File creation for `workspace.local.toml` lives here, not in generic bootstrap. |
| `src/meridian/lib/ops/config_surface.py` | Shared builder for `config show` and `doctor` workspace/config surfacing payloads so both commands report the same state vocabulary. |

## Design Notes

- The workspace file should be locally ignored without requiring a committed project-file diff. The project-root abstraction should own that policy because it is a property of a project-root local file, not of `.meridian/`.
- `ProjectPaths` should expose file locations only. Mutation policies live in the loader and command layers.
- `resolve_repo_root` is renamed to `resolve_project_root` during R01 to align the internal name with the concept. No user-facing "repo root" term exists.

## Open Questions

None at the architecture level.
