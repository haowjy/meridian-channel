# Architecture: Storage Boundaries and Workspace

## On-Disk Ownership Map

```
<repo_root>/
├── meridian.toml            # [NEW] Committed project config (replaces .meridian/config.toml)
├── mars.toml                # [UNCHANGED] Committed package manifest
├── mars.lock                # [UNCHANGED] Committed package lockfile
├── mars.local.toml          # [UNCHANGED] Local package overrides (gitignored)
├── workspace.toml           # [NEW] Local workspace topology (gitignored)
├── .agents/                 # [UNCHANGED] Generated output from mars sync
│
├── .meridian/               # Meridian runtime + artifact state
│   ├── .gitignore           # [REVISED] Simplified — fewer tracked exceptions
│   ├── fs/                  # [TRANSITIONAL] Committed shared knowledge (future: cloud)
│   ├── work/                # [TRANSITIONAL] Committed work artifacts (future: cloud)
│   ├── work-archive/        # [TRANSITIONAL] Archived work artifacts (future: cloud)
│   ├── work-items/          # Local work item metadata
│   ├── spawns.jsonl          # Local spawn event store
│   ├── sessions.jsonl        # Local session event store
│   ├── spawns/              # Per-spawn artifact directories
│   ├── sessions/            # Per-session data
│   ├── cache/               # Runtime cache
│   ├── config.toml          # [DEPRECATED] Legacy config location — fallback only
│   └── models.toml          # [DEPRECATED] Legacy models location — migrate to meridian.toml
│
├── .mars/                   # [FUTURE] Mars local runtime state (if Mars needs it)
│   └── ...                  # sync cache, integrity, etc. — Mars-owned
```

### Classification Matrix

| File | Owner | Committed? | Purpose |
|------|-------|-----------|---------|
| `meridian.toml` | Meridian | Yes | Project operational config |
| `mars.toml` | Mars | Yes | Package dependencies |
| `mars.lock` | Mars | Yes | Resolved package state |
| `mars.local.toml` | Mars | No | Local package overrides |
| `workspace.toml` | Meridian | No | Local workspace topology |
| `.agents/` | Mars | No (generated) | Materialized agent packages |
| `.meridian/fs/` | Meridian | Yes (transitional) | Shared codebase knowledge until shared/cloud backend exists |
| `.meridian/work/` | Meridian | Yes (transitional) | Work-scoped artifacts until shared/cloud backend exists |
| `.meridian/work-archive/` | Meridian | Yes (transitional) | Archived work artifacts until shared/cloud backend exists |
| `.meridian/spawns.*` | Meridian | No | Runtime spawn state |
| `.meridian/sessions.*` | Meridian | No | Runtime session state |
| `.meridian/config.toml` | Meridian | Deprecated | Legacy config fallback |

---

## Config Migration: `.meridian/config.toml` → `meridian.toml`

### Why Move

1. **Repo hygiene.** Committed project policy belongs at the repo root alongside `mars.toml`, `pyproject.toml`, etc. Burying it inside a mostly-gitignored directory behind a gitignore exception is an anti-pattern.

2. **Discoverability.** Developers `ls` the repo root to understand project structure. A `meridian.toml` at root is immediately visible. `.meridian/config.toml` requires knowing the internal layout.

3. **Simplified `.meridian/.gitignore`.** Today the gitignore tracks `config.toml` as an exception. Moving config to root eliminates this exception, making `.meridian/` closer to its intended long-term role as a pure local/runtime-state directory.

4. **Consistency with Mars.** `mars.toml` is at root. `meridian.toml` at root creates a consistent pattern.

### Migration Strategy

```
Load order:
1. <repo_root>/meridian.toml     (new canonical location)
2. .meridian/config.toml          (legacy fallback)
3. If both exist → meridian.toml wins, advisory emitted once
```

The `_resolve_project_toml` function in `settings.py` changes from:

```python
def _resolve_project_toml(repo_root: Path) -> Path | None:
    config_path = resolve_state_paths(repo_root).config_path
    if config_path.is_file():
        return config_path
    return None
```

To:

```python
def _resolve_project_toml(repo_root: Path) -> Path | None:
    # New canonical location
    root_config = repo_root / "meridian.toml"
    if root_config.is_file():
        legacy_config = resolve_state_paths(repo_root).config_path
        if legacy_config.is_file():
            logger.info(
                "Both meridian.toml and .meridian/config.toml exist; "
                "using meridian.toml. Run 'meridian config migrate' to clean up."
            )
        return root_config

    # Legacy fallback
    legacy_config = resolve_state_paths(repo_root).config_path
    if legacy_config.is_file():
        return legacy_config
    return None
```

### Schema: No Changes

`meridian.toml` uses the exact same TOML schema as `.meridian/config.toml`. The file just moves. This means:

```toml
# meridian.toml — at repo root, committed

[defaults]
primary_agent = "dev-orchestrator"

[timeouts]
kill_grace_minutes = 0.033

[harness]
# claude = ""
# codex = ""

[primary]
# autocompact_pct = 65

[output]
# show = ["lifecycle", "sub-run", "error", "system"]
```

### Models Integration

`models.toml` currently lives at `.meridian/models.toml`. Two options:

**Option A: Absorb into `meridian.toml`** — Add a `[models]` section. Keeps everything in one file. Risk: `models.toml` schema has `[aliases]`, `[metadata.*]`, `[harness_patterns]`, `[model_visibility]` tables that don't conflict with existing config sections but add bulk.

**Option B: Keep as separate `models.toml` at root** — Move to `<repo_root>/models.toml` alongside `meridian.toml`. Same migration pattern: check root first, fall back to `.meridian/models.toml`.

**Recommendation: Option B.** The model catalog schema is orthogonal to operational config and has its own top-level sections that would nest awkwardly under `[models]`. Separate file preserves clarity. Migration is the same pattern.

---

## `.meridian/.gitignore` Simplification

### Current State

```gitignore
*
!.gitignore
!config.toml        # ← remove (config moves to root)
!fs/
!fs/**
!work/
!work/**
!work-archive/
!work-archive/**
```

### Target State

```gitignore
*
!.gitignore
!fs/
!fs/**
!work/
!work/**
!work-archive/
!work-archive/**
```

The `config.toml` exception is removed. If `models.toml` moves to root (Option B), the `models.toml` exception (if one exists) is also removed.

### Future: What Happens to fs/, work/, and work-archive/?

The tracked exceptions for `fs/`, `work/`, and `work-archive/` remain for now. These are committed shared artifacts only because Meridian does not yet have a cloud/shared backend for them. They should be treated as transitional compatibility state, not as precedent for adding more committed content under `.meridian/`. If/when they migrate to cloud-backed storage:

1. The gitignore exceptions go away.
2. `.meridian/` becomes fully gitignored (just `*`).
3. `.meridian/.gitignore` itself may become unnecessary.

The current design does not depend on these directories being committed. Their gitignore-exception nature is an implementation detail of the current storage backend, not a load-bearing architectural choice.

---

## Workspace: `workspace.toml`

### Schema

```toml
# workspace.toml — at repo root, gitignored
# Declares directories to inject into harness launches as additional context roots.

[context-roots."meridian-flow/meridian-base"]
path = "../prompts/meridian-base"

[context-roots."meridian-flow/meridian-dev-workflow"]
path = "../prompts/meridian-dev-workflow"

[context-roots.shared-data]
path = "/data/team-shared"
enabled = false  # temporarily disabled
```

### Why `[context-roots]` Instead of `[repos]`

The previous design used `[repos]` which implies git repositories. But the actual use case is broader: developers want to inject *any directory* into harness context. A shared data directory, a monorepo subtree, a documentation checkout — none of these need to be git repos. `[context-roots]` names the concept accurately: these are additional context roots for harness launches.

Keys can be:
- `org/repo` canonical identifiers (for repos that correspond to mars.toml dependencies)
- Arbitrary descriptive slugs (for non-repo directories)

### Why Not a `[settings]` Table

The previous design included `[settings]` for future workspace-wide settings. This design deliberately omits it. Operational settings belong in `meridian.toml`. The workspace file is purely topology — which directories participate. Adding a settings table invites scope creep where workspace becomes a parallel config surface.

If a future need arises for per-workspace operational overrides (e.g., workspace-level model preference), that need should be evaluated against extending `meridian.toml` with an optional local overlay, not against making `workspace.toml` a settings file.

### Runtime Model

```
Module: src/meridian/lib/config/workspace.py

WorkspaceConfig (frozen Pydantic model)
├── context_roots: dict[str, ContextRoot]
│   └── ContextRoot
│       ├── path: Path      # resolved absolute
│       ├── enabled: bool   # default True
│       └── exists: bool    # validated at load
│
load_workspace(repo_root: Path) → WorkspaceConfig | None
context_directories(ws: WorkspaceConfig) → list[Path]
    # returns paths where enabled=True and exists=True
```

---

## Context-Root Injection Architecture

### Integration Point

The primary integration is in harness preflight. Today, `claude_preflight.py::expand_claude_passthrough_args` handles cross-CWD `--add-dir` injection and parent settings inheritance. Workspace injection adds a third source.

```
Current flow:
  expand_claude_passthrough_args
    1. --add-dir <execution_cwd>       (cross-CWD spawns)
    2. parent additionalDirectories    (from settings.json)
    → dedupe_nonempty → return

Revised flow:
  expand_claude_passthrough_args
    1. workspace context_directories   (from workspace.toml) [NEW]
    2. --add-dir <execution_cwd>       (cross-CWD spawns)
    3. parent additionalDirectories    (from settings.json)
    → dedupe_nonempty → return
```

Workspace directories go first so that parent settings and explicit passthrough can override (last-wins). This ordering means workspace roots act as defaults that more specific sources can override.

### Cross-Harness Injection

For Claude, injection is `--add-dir`. For Codex and OpenCode, no equivalent directory-inclusion flag exists today. The architecture accommodates future harness support:

1. `context_directories()` returns a `list[Path]` — harness-agnostic.
2. Each harness adapter's preflight or projection consumes the list through its own mechanism.
3. Harnesses without a mechanism silently skip the roots.

When Codex/OpenCode add directory context features, the only change is in their projection module — the workspace config and path resolution are already in place.

### Where WorkspaceConfig Is Loaded

WorkspaceConfig loads lazily at harness preflight time, not at MeridianConfig load time. Reasons:
- Workspace is consumed by harness operations, not by config resolution.
- Lazy load avoids overhead for commands that don't launch harnesses.
- Keeps workspace orthogonal to the config precedence chain.

### Spawn Propagation

Workspace context-roots propagate to child spawns automatically through the existing parent permission inheritance:
- Parent Claude process gets `--add-dir` flags from workspace
- `read_parent_claude_permissions` reads parent's `settings.json` which includes `additionalDirectories`
- Child spawns inherit these directories
- No additional workspace-aware propagation needed

---

## Relationship to mars.local.toml

Unchanged from prior design. Key points:

| Concern | Owner | File |
|---------|-------|------|
| Package sync local path overrides | Mars | `mars.local.toml` |
| Workspace topology / context-root injection | Meridian | `workspace.toml` |

`meridian workspace sync-mars` bridges them: reads workspace context-roots whose keys match `mars.toml` dependency URLs (by `org/repo` extraction) and generates corresponding `mars.local.toml` `[overrides]` entries.

---

## AGENTS.md Migration

Current:
```markdown
- `~/gitrepos/meridian-cli`
- `~/gitrepos/prompts/meridian-base`
- `~/gitrepos/prompts/meridian-dev-workflow`
```

Revised:
```markdown
Source repos:
- **`meridian-flow/meridian-base`** — core agents, skills, spawn infrastructure
- **`meridian-flow/meridian-dev-workflow`** — dev orchestration agents and skills

Configure `workspace.toml` to map these to local checkouts.
```

Canonical identifiers are stable across developers. Workspace resolution maps them to local paths.

---

## Future: Cloud/Shared State

The current design keeps `fs/` and `work/` as committed directories under `.meridian/`. This is a pragmatic choice for now — git provides versioning, collaboration, and persistence without additional infrastructure.

When cloud-backed state becomes viable:

1. **`fs/`** — could be backed by a shared knowledge store. The interface (`$MERIDIAN_FS_DIR` pointing to a local directory) stays the same; the sync mechanism changes.
2. **`work/`** — could be backed by a work-item service. Work item metadata already uses per-file JSON; migration to an API is structurally simple.
3. **`.meridian/.gitignore`** — simplifies to a blanket `*` with no exceptions.
4. **Team workspace** — a committed `workspace.toml` (or `workspace.team.toml`) could declare shared context-roots by canonical identity, with team members' local `workspace.toml` providing filesystem resolution.

None of these transitions require changing the repo-root config pattern, the workspace schema, or the context-root injection architecture. The design is cloud-evolution-neutral.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `meridian.toml` parse error | Fatal with clear message |
| `workspace.toml` parse error | Fatal with clear message — developer explicitly created it |
| No `meridian.toml` or `.meridian/config.toml` | Use defaults |
| No `workspace.toml` | All workspace features inert, zero overhead |
| Both config locations exist | `meridian.toml` wins, advisory once |
| Context-root path doesn't exist | Warning, root skipped, `doctor` reports |
| Unknown keys in workspace.toml | Preserved, debug log |
