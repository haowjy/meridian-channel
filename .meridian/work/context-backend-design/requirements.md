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
path = "~/.meridian/context/{project}/work"
auto_pull = true
auto_commit = true
auto_push = true

[context.kb]
source = "local"
path = ".meridian/kb"
```

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

### Git Sync Layer

Optional sync for git-backed context folders:

```toml
[context.work]
source = "git"
path = "~/.meridian/context/{project}/work"
auto_pull = true       # pull on session start
auto_commit = true     # commit on work item changes
auto_push = true       # push after commit
pull_strategy = "rebase"
on_conflict = "commit_markers"
```

### Sync Behavior

| Setting | When | Action |
|---------|------|--------|
| `auto_pull` | Session start, `meridian work` | `git pull --rebase` |
| `auto_commit` | Work item written | `git add . && git commit -m "work: <item>"` |
| `auto_push` | After commit | `git push` |

### Conflict Handling

On rebase conflict:
1. File contains `<<<<<<<` conflict markers
2. Commit anyway with markers
3. Push
4. User or AI resolves markers on future pass

No data loss, explicit visibility, manual resolution.

### CLI

```bash
$ meridian context
work: /home/user/.meridian/context/project/work
kb: /home/user/repo/.meridian/kb

$ meridian context work
/home/user/.meridian/context/project/work

$ meridian context sync work        # manual pull + push
$ meridian context sync work --pull # just pull
$ meridian context sync work --push # just push
```

## Success Criteria

1. Zero config = current behavior unchanged (with `fs` → `kb` rename)
2. Both `work` and `kb` always present, even with zero config
3. Single global config line externalizes work/kb for all repos
4. Git sync is transparent — pull/commit/push happen automatically
5. Conflicts are visible, never silent data loss
6. `meridian context` shows resolved paths clearly
7. `MERIDIAN_FS_DIR` works as deprecated alias for `MERIDIAN_KB_DIR`
8. Existing `.meridian/fs/` directories work via fallback with deprecation warning
