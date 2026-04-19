# Context Backend Technical Architecture

## Overview

The context backend introduces a resolution layer between config and path usage, enabling work items to live outside the repo while fs docs remain in-repo. An optional git sync layer provides automatic push/pull for git-backed context directories.

---

## Config Schema

### TOML Structure

```toml
# meridian.toml, meridian.local.toml, or ~/.meridian/config.toml

[context.work]
source = "git"                              # "local" | "git"
path = "~/.meridian/context/{project}/work"
auto_pull = true                            # git only
auto_commit = true                          # git only
auto_push = true                            # git only
pull_strategy = "rebase"                    # git only: "rebase" | "merge"
on_conflict = "commit_markers"              # git only: only supported strategy

[context.fs]
source = "local"
path = ".meridian/fs"
```

### Defaults (no config)

```toml
[context.work]
source = "local"
path = ".meridian/work"

[context.fs]
source = "local"
path = ".meridian/fs"
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
    path: str = ".meridian/work"  # or ".meridian/fs" for fs
    
    # Git-only options (ignored when source = "local")
    auto_pull: bool = False
    auto_commit: bool = False
    auto_push: bool = False
    pull_strategy: Literal["rebase", "merge"] = "rebase"
    on_conflict: Literal["commit_markers"] = "commit_markers"

class ContextConfig(BaseModel):
    """Arbitrary context types via __pydantic_extra__."""
    model_config = ConfigDict(frozen=True, extra="allow")
    
    work: ContextPathConfig = Field(
        default_factory=lambda: ContextPathConfig(path=".meridian/work")
    )
    fs: ContextPathConfig = Field(
        default_factory=lambda: ContextPathConfig(path=".meridian/fs")
    )
    
    # Additional contexts captured in __pydantic_extra__
    # e.g., context.docs, context.research
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
    work_config: ContextPathConfig
    fs_root: Path
    fs_source: ContextSourceType
    fs_config: ContextPathConfig
    extra: dict[str, tuple[Path, ContextPathConfig]]  # arbitrary contexts

def resolve_context(
    repo_root: Path,
    config: ContextConfig,
) -> ResolvedContext:
    """Resolve context paths from config + repo root."""
    
    project_uuid = get_project_uuid(repo_root / ".meridian")
    
    work_root = _resolve_path(config.work.path, repo_root, project_uuid)
    fs_root = _resolve_path(config.fs.path, repo_root, project_uuid)
    
    # Resolve arbitrary contexts
    extra = {}
    for name, cfg in config.__pydantic_extra__.items():
        path = _resolve_path(cfg.path, repo_root, project_uuid)
        extra[name] = (path, cfg)
    
    return ResolvedContext(
        work_root=work_root,
        work_source=config.work.source,
        work_config=config.work,
        fs_root=fs_root,
        fs_source=config.fs.source,
        fs_config=config.fs,
        extra=extra,
    )

def _resolve_path(
    path_spec: str,
    repo_root: Path,
    project_uuid: str | None,
) -> Path:
    """Resolve one context path specification."""
    
    # Substitute {project}
    if "{project}" in path_spec:
        if project_uuid is None:
            project_uuid = get_or_create_project_uuid(repo_root / ".meridian")
        path_spec = path_spec.replace("{project}", project_uuid)
    
    # Expand ~ and resolve
    expanded = Path(path_spec).expanduser()
    if expanded.is_absolute():
        return expanded
    return repo_root / expanded
```

---

## Git Sync Layer

### Sync Operations

```python
# src/meridian/lib/context/git_sync.py

@dataclass(frozen=True)
class SyncResult:
    success: bool
    operation: str
    message: str
    conflicts: list[str] = field(default_factory=list)

def sync_pull(context_dir: Path, strategy: str = "rebase") -> SyncResult:
    """Execute git pull on context directory."""
    
    if not (context_dir / ".git").exists():
        return SyncResult(False, "pull", "not a git repository")
    
    try:
        flag = "--rebase" if strategy == "rebase" else "--no-rebase"
        subprocess.run(
            ["git", "pull", flag],
            cwd=context_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return SyncResult(True, "pull", "ok")
    except subprocess.CalledProcessError as e:
        conflicts = _find_conflict_files(context_dir)
        if conflicts:
            # Commit with markers
            _commit_with_conflicts(context_dir, conflicts)
            return SyncResult(True, "pull", "conflicts committed", conflicts)
        return SyncResult(False, "pull", e.stderr)

def sync_commit(context_dir: Path, message: str) -> SyncResult:
    """Stage all and commit."""
    # ... implementation

def sync_push(context_dir: Path) -> SyncResult:
    """Push to remote."""
    # ... implementation
```

### Conflict Handling Flow

```
git pull --rebase
    │
    ├─ success → done
    │
    └─ conflict →
         │
         ├─ git add .
         ├─ git rebase --continue (or abort + merge)
         ├─ commit with markers
         └─ push
              │
              └─ User/AI resolves markers later
```

### Trigger Points

| Event | Condition | Action |
|-------|-----------|--------|
| Session start | `source = "git"` AND `auto_pull = true` | pull |
| Work item write | `source = "git"` AND `auto_commit = true` | add + commit |
| Post-commit | `source = "git"` AND `auto_push = true` | push |
| `meridian context sync` | `source = "git"` | manual pull + push |
| `meridian context sync` | `source = "local"` | no-op with message |

---

## CLI Surface

### Command Structure

```
meridian context                    # show resolved paths (simple)
meridian context <name>             # show single context path (just path)
meridian context --verbose          # show config details
meridian context sync <target>      # sync work or fs
meridian context sync <target> --pull
meridian context sync <target> --push
meridian context migrate <target>   # move to configured path
```

### Output Format

Default — minimal for agents:

```
$ meridian context
work: /home/jimmy/.meridian/context/abc123/work
fs: /home/jimmy/gitrepos/meridian-cli/.meridian/fs
docs: /home/jimmy/shared-docs/abc123
research: /home/jimmy/private-research/abc123
```

Single context — just the path:

```
$ meridian context work
/home/jimmy/.meridian/context/abc123/work
```

Verbose — config details:

```
$ meridian context --verbose
work:
  source: git
  path: ~/.meridian/context/{project}/work
  resolved: /home/jimmy/.meridian/context/abc123/work
  sync: auto_pull, auto_commit, auto_push (last: 2m ago)

fs:
  source: local
  path: .meridian/fs
  resolved: /home/jimmy/gitrepos/meridian-cli/.meridian/fs

docs:
  source: local
  path: ~/shared-docs/{project}
  resolved: /home/jimmy/shared-docs/abc123
```

---

## Environment Variables

For spawns, all contexts are exported:

```bash
MERIDIAN_WORK_DIR=/home/jimmy/.meridian/context/abc123/work/current-item
MERIDIAN_FS_DIR=/home/jimmy/gitrepos/meridian-cli/.meridian/fs
MERIDIAN_CONTEXT_DOCS_DIR=/home/jimmy/shared-docs/abc123
MERIDIAN_CONTEXT_RESEARCH_DIR=/home/jimmy/private-research/abc123
```

`work` and `fs` keep their special env var names for backward compatibility. Custom contexts use `MERIDIAN_CONTEXT_<NAME>_DIR`.

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
│   └── git_sync.py            # sync_pull, sync_commit, sync_push
└── ops/
    └── context.py             # context_show, context_sync, context_migrate

src/meridian/cli/
└── context_cmd.py             # CLI commands
```

---

## Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| No `[context]` in any config | `source = "local"`, paths = `.meridian/work` and `.meridian/fs` |
| `MERIDIAN_WORK_DIR` set explicitly | Env var wins over config |
| Config set but directory missing | Created on first use |

---

## Error Handling

| Error | Response |
|-------|----------|
| Git not installed | Warning, skip sync, continue |
| Network unreachable | Warning, skip push/pull, continue |
| Conflict markers | Commit with markers, push, log warning |
| Invalid source type | Error on startup, refuse to run |
| Migration destination not empty | Error, suggest --force |
