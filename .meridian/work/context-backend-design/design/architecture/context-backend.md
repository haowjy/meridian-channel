# Context Backend Technical Architecture

## Overview

The context backend introduces a resolution layer between config and path usage, enabling work items and agent memory to live outside the repo. Two built-in contexts (`work` and `kb`) are always present; arbitrary contexts can be added via config.

- **`work`** — ephemeral work-item context (design, plans, decisions for current task)
- **`kb`** — persistent agent memory (accumulated learnings, codebase knowledge, decision history)

Git sync is handled by the `git-autosync` hook (see hook-system-design).

---

## Config Schema

### TOML Structure

```toml
# meridian.toml, meridian.local.toml, or ~/.meridian/config.toml

[context.work]
source = "git"                              # "local" | "git"
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

### Defaults (no config)

```toml
[context.work]
source = "local"
path = ".meridian/work"

[context.kb]
source = "local"
path = ".meridian/kb"
```

### Path Value Semantics

| Value | Resolution |
|-------|------------|
| `".meridian/work"` | Relative to repo root |
| `"~/..."` | Expands `~` to home directory |
| `"/..."` | Absolute path, used as-is |
| `"{project}"` | Substituted with project UUID from `.meridian/id` |

### Config Models

```python
# src/meridian/lib/config/context_config.py

class ContextSourceType(str, Enum):
    LOCAL = "local"
    GIT = "git"

class ContextPathConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    source: ContextSourceType = ContextSourceType.LOCAL
    path: str  # default varies by context type

class ContextConfig(BaseModel):
    """Built-in contexts + arbitrary via __pydantic_extra__."""
    model_config = ConfigDict(frozen=True, extra="allow")
    
    work: ContextPathConfig = Field(
        default_factory=lambda: ContextPathConfig(path=".meridian/work")
    )
    kb: ContextPathConfig = Field(
        default_factory=lambda: ContextPathConfig(path=".meridian/kb")
    )
```

---

## Resolution Layer

### Path Resolver

```python
# src/meridian/lib/context/resolver.py

@dataclass(frozen=True)
class ResolvedContext:
    work_root: Path
    work_source: ContextSourceType
    kb_root: Path
    kb_source: ContextSourceType
    extra: dict[str, tuple[Path, ContextPathConfig]]

def resolve_context(
    repo_root: Path,
    config: ContextConfig,
) -> ResolvedContext:
    """Resolve context paths from config + repo root."""
    
    project_uuid = get_project_uuid(repo_root / ".meridian")
    
    work_root = _resolve_path(config.work.path, repo_root, project_uuid)
    kb_root = _resolve_path(config.kb.path, repo_root, project_uuid)
    
    # Resolve arbitrary contexts
    extra = {}
    for name, cfg in config.__pydantic_extra__.items():
        path = _resolve_path(cfg.path, repo_root, project_uuid)
        extra[name] = (path, cfg)
    
    return ResolvedContext(
        work_root=work_root,
        work_source=config.work.source,
        kb_root=kb_root,
        kb_source=config.kb.source,
        extra=extra,
    )
```

---

## Git Source Setup

When `source = "git"`, on first access:

```python
def ensure_git_context(path: Path) -> Path:
    """Ensure context path exists and resolve enclosing git repo root."""

    path.mkdir(parents=True, exist_ok=True)
    repo_root = discover_git_repo_root(path)

    if repo_root is None:
        raise ContextConfigError(
            f"context path '{path}' is not inside a git repo; "
            "point it at a subfolder in an existing repo"
        )

    return repo_root

def discover_git_repo_root(start: Path) -> Path | None:
    current = start
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
```

Git sync (pull/commit/push) is handled by the `git-autosync` hook, not here.
Staging is scoped per-context via `git add .` with `cwd=<context-path>`.

---

## Environment Variables

For spawns, all contexts are exported:

```bash
MERIDIAN_WORK_DIR=/home/user/gitrepos/meridian-docs/meridian-cli/work/current-item
MERIDIAN_KB_DIR=/home/user/gitrepos/meridian-docs/meridian-cli/kb
MERIDIAN_CONTEXT_DOCS_DIR=/home/user/gitrepos/meridian-docs/general
```

`work` and `kb` keep their special env var names. Custom contexts use `MERIDIAN_CONTEXT_<NAME>_DIR`.

---

## File Layout

```
src/meridian/lib/
├── config/
│   ├── context_config.py      # ContextConfig, ContextPathConfig
│   └── settings.py            # Extended to load [context] section
├── context/
│   ├── __init__.py
│   ├── resolver.py            # ResolvedContext, resolve_context()
│   ├── compat.py              # Legacy fs/ detection and fallback
│   └── setup.py               # Git context path setup + repo root discovery
└── ops/
    └── context.py             # context_show CLI
```

---

## Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| No `[context]` in any config | `source = "local"`, paths = `.meridian/work` and `.meridian/kb` |
| `MERIDIAN_WORK_DIR` set explicitly | Env var wins over config |
| `MERIDIAN_KB_DIR` set explicitly | Env var wins over config |
| `MERIDIAN_FS_DIR` set explicitly | Treated as alias for `MERIDIAN_KB_DIR` (deprecated warning) |
| Config set but directory missing | Created on first use |

---

## CLI Surface

### Command Structure

```
meridian context                    # show resolved paths
meridian context <name>             # show single context path
meridian context --verbose          # show config details
```

### Output Format

Default — minimal for agents:

```
$ meridian context
work: /home/user/gitrepos/meridian-docs/meridian-cli/work (git)
kb: /home/user/gitrepos/meridian-docs/meridian-cli/kb (git)
```

Single context — just the path:

```
$ meridian context work
/home/user/gitrepos/meridian-docs/meridian-cli/work
```

Verbose — config details:

```
$ meridian context --verbose
work:
  source: git
  path: ~/gitrepos/meridian-docs/meridian-cli/work
  resolved: /home/user/gitrepos/meridian-docs/meridian-cli/work

kb:
  source: git
  path: ~/gitrepos/meridian-docs/meridian-cli/kb
  resolved: /home/user/gitrepos/meridian-docs/meridian-cli/kb
```

---

## Integration with Hook System

When `source = "git"` is configured, the hook system auto-registers `git-autosync`:

```python
# In hook registry initialization
def auto_register_git_hooks(context_config: ContextConfig) -> list[Hook]:
    """Auto-register git-autosync for git-sourced contexts."""
    
    git_contexts = []
    
    if context_config.work.source == ContextSourceType.GIT:
        git_contexts.append("work")
    if context_config.kb.source == ContextSourceType.GIT:
        git_contexts.append("kb")
    for name, cfg in context_config.__pydantic_extra__.items():
        if cfg.source == ContextSourceType.GIT:
            git_contexts.append(name)
    
    if not git_contexts:
        return []
    
    return [Hook(
        name="git-autosync",
        event="context.touched",
        builtin="git-autosync",
        interval="10m",
    )]
```

`git-autosync` stages with `git add .` and runs in each context path as working directory. This avoids cross-project staging in a shared docs repo.

See hook-system-design for `git-autosync` implementation.
