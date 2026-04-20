# Context Backend Design

## Problem

Work items (`work/`, `work-archive/`) contain business context — strategy, direction, design decisions — that shouldn't be published in public repos. Currently these live in `.meridian/` and get pushed to GitHub.

The knowledge base (`kb/`) is persistent agent memory — accumulated learnings, codebase understanding, decision history. It may also need to be externalized for privacy or sync across machines.

## Requirements

### Separation of Concerns

- `kb/` (formerly `fs/`) is the persistent agent memory layer
- `work/` and `work-archive/` are ephemeral work-item context
- Both can be externalized to private locations

### Two Built-in Contexts

Both `work` and `kb` are always present, even with zero config:

| Context | Purpose | Default Path | Env Var |
|---------|---------|--------------|---------|
| `work` | Ephemeral work-item context | `.meridian/work` | `MERIDIAN_WORK_DIR` |
| `kb` | Persistent agent memory | `.meridian/kb` | `MERIDIAN_KB_DIR` |

### Configuration

Config precedence (highest to lowest):
1. `meridian.local.toml` — personal, gitignored
2. `meridian.toml` — repo default, checked in
3. `~/.meridian/config.toml` — global fallback

Each context type independently configurable:

```toml
[context.work]
source = "git"
path = "~/gitrepos/meridian-docs/meridian-cli/work"

[context.kb]
source = "git"
path = "~/gitrepos/meridian-docs/meridian-cli/kb"
```

Shared docs repo model:

```text
~/gitrepos/meridian-docs/
├── meridian-cli/
│   ├── work/
│   └── kb/
├── other-project/
│   ├── work/
│   └── kb/
└── general/
```

One git repo backs multiple projects. Each project points `context.work.path` and `context.kb.path` at its own subfolders inside that shared repo.

### Source Types

| Source | Behavior |
|--------|----------|
| `local` | Just a path, no sync. User manages (Dropbox, iCloud, manual). |
| `git` | Git-managed. Auto-registers `git-autosync` hook. Git repo root is auto-discovered by walking up from `path` to the nearest `.git/` parent. |

Future sources: `s3`, `meridian` (managed sync service).

### Git Source Behavior

When `source = "git"`:

1. **On `meridian init` / first spawn**:
   - Ensure context path exists
   - Discover git repo root by walking up from context path to nearest parent containing `.git/`
   - If no repo root is found: fail with actionable error (context path must live inside an existing git repo)
   
2. **Auto-registers `git-autosync` hook** (see hook-system-design):
   - Syncs all `source = "git"` contexts
   - Default interval: 10 minutes
   - User can override via `[[hooks]]` config
   - Stages context changes with `git add .` using `cwd=<context-path>` so staging stays scoped to that context subtree

### Arbitrary Contexts

Users can define additional contexts:

```toml
[context.docs]
source = "local"
path = "~/shared-docs/{project}"

[context.research]
source = "git"
path = "~/.meridian/research/{project}"
```

Custom contexts export as `MERIDIAN_CONTEXT_<NAME>_DIR`.

### Defaults

- `kb`: `source = "local"`, `path = ".meridian/kb"`
- `work`: `source = "local"`, `path = ".meridian/work"`
- No config = current behavior, nothing changes (except `fs` → `kb` rename)

### CLI

The existing `meridian context` command is extended (not replaced) to show the context catalog alongside runtime info:

```bash
$ meridian context
repo_root: /home/user/gitrepos/meridian-cli
state_root: /home/user/.meridian/projects/abc123
depth: 0

contexts:
  work: /home/user/gitrepos/meridian-docs/meridian-cli/work (git)
  kb: /home/user/gitrepos/meridian-docs/meridian-cli/kb (git)

$ meridian context work
/home/user/gitrepos/meridian-docs/meridian-cli/work

$ meridian context --verbose
repo_root: /home/user/gitrepos/meridian-cli
state_root: /home/user/.meridian/projects/abc123
depth: 0

contexts:
  work:
    source: git
    path: ~/gitrepos/meridian-docs/meridian-cli/work
    resolved: /home/user/gitrepos/meridian-docs/meridian-cli/work
  kb:
    source: git
    path: ~/gitrepos/meridian-docs/meridian-cli/kb
    resolved: /home/user/gitrepos/meridian-docs/meridian-cli/kb
```

This replaces the current `work_dir` and `fs_dir` fields with a unified `contexts` section.

## Success Criteria

1. Zero config = current behavior unchanged (with `fs` → `kb` rename)
2. Both `work` and `kb` always present, even with zero config
3. Single global config line externalizes work/kb for all repos
4. `source = "git"` auto-registers `git-autosync` hook (see hook-system-design)
5. `meridian context` shows resolved paths clearly
6. `MERIDIAN_FS_DIR` works as deprecated alias for `MERIDIAN_KB_DIR`
7. Existing `.meridian/fs/` directories work via fallback with deprecation warning
8. Shared docs repo model is first-class: context paths may be subfolders of a single multi-project git repo
9. Git source behavior discovers repo root automatically from configured context path

## Dependencies

- **hook-system-design**: Git sync behavior implemented via `git-autosync` built-in hook

## Implementation Notes

### work-archive Handling

When `context.work` is externalized, `work-archive/` follows automatically as a sibling:
- If `context.work.path = ~/docs/proj/work`, then archive lives at `~/docs/proj/work-archive/`
- Archive is NOT a separate context — it's an implementation detail of work lifecycle
- `meridian work done` moves items from `work/` to `work-archive/` within the same parent

### Hook Payload for git-autosync

The `git-autosync` hook needs to sync ALL git-backed contexts, not just `work_dir`. Implementation:

1. Extend `HookContext` with `git_context_paths: tuple[str, ...]` — all paths where `source = "git"`
2. `git-autosync` iterates this list, runs `git add .` from each path
3. Auto-registration happens once per git repo root (not per context) to avoid duplicate syncs

### Config Loading

`meridian.local.toml` support (implementation in progress):
- Precedence: `meridian.local.toml` > `meridian.toml` > `~/.meridian/config.toml`
- Local file is gitignored by default
- Unknown sections like `[context]` will be parsed once config schema is extended
