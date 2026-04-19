# Context Backend Technical Architecture

## Overview

The context backend introduces a resolution layer between config and path usage, enabling work items and agent memory to live outside the repo. Two built-in contexts (`work` and `kb`) are always present; arbitrary contexts can be added via config.

- **`work`** — ephemeral work-item context (design, plans, decisions for current task)
- **`kb`** — persistent agent memory (accumulated learnings, codebase knowledge, decision history)

An optional git sync layer provides automatic push/pull for git-backed context directories.

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

[context.kb]
source = "local"
path = ".meridian/kb"
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
    
    # Git-only options (ignored when source = "local")
    auto_pull: bool = False
    auto_commit: bool = False
    auto_push: bool = False
    pull_strategy: Literal["rebase", "merge"] = "rebase"
    on_conflict: Literal["commit_markers"] = "commit_markers"

class ContextConfig(BaseModel):
    """Built-in contexts + arbitrary via __pydantic_extra__."""
    model_config = ConfigDict(frozen=True, extra="allow")
    
    work: ContextPathConfig = Field(
        default_factory=lambda: ContextPathConfig(path=".meridian/work")
    )
    kb: ContextPathConfig = Field(
        default_factory=lambda: ContextPathConfig(path=".meridian/kb")
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
    kb_root: Path
    kb_source: ContextSourceType
    kb_config: ContextPathConfig
    extra: dict[str, tuple[Path, ContextPathConfig]]  # arbitrary contexts

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
        work_config=config.work,
        kb_root=kb_root,
        kb_source=config.kb.source,
        kb_config=config.kb,
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
meridian context sync <target>      # sync work or kb
meridian context sync <target> --pull
meridian context sync <target> --push
meridian context migrate <target>   # move to configured path
```

### Output Format

Default — minimal for agents:

```
$ meridian context
work: /home/jimmy/.meridian/context/abc123/work
kb: /home/jimmy/gitrepos/meridian-cli/.meridian/kb
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

kb:
  source: local
  path: .meridian/kb
  resolved: /home/jimmy/gitrepos/meridian-cli/.meridian/kb

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
MERIDIAN_KB_DIR=/home/jimmy/gitrepos/meridian-cli/.meridian/kb
MERIDIAN_CONTEXT_DOCS_DIR=/home/jimmy/shared-docs/abc123
MERIDIAN_CONTEXT_RESEARCH_DIR=/home/jimmy/private-research/abc123
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
| No `[context]` in any config | `source = "local"`, paths = `.meridian/work` and `.meridian/kb` |
| `MERIDIAN_WORK_DIR` set explicitly | Env var wins over config |
| `MERIDIAN_KB_DIR` set explicitly | Env var wins over config |
| `MERIDIAN_FS_DIR` set explicitly | Treated as alias for `MERIDIAN_KB_DIR` (deprecated warning) |
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

---

## Legacy fs/ Detection and Fallback

### Detection Logic

```python
# src/meridian/lib/context/compat.py

def resolve_kb_path_with_fallback(repo_root: Path) -> tuple[Path, bool]:
    """Resolve kb path, falling back to fs/ if kb/ doesn't exist.
    
    Returns (path, is_legacy) tuple.
    """
    meridian_dir = repo_root / ".meridian"
    kb_dir = meridian_dir / "kb"
    fs_dir = meridian_dir / "fs"
    
    if kb_dir.exists():
        if fs_dir.exists():
            logger.warning(
                "Both .meridian/fs/ and .meridian/kb/ exist. "
                "Using kb/, consider removing orphaned fs/."
            )
        return (kb_dir, False)
    
    if fs_dir.exists():
        logger.warning(
            "Detected .meridian/fs/ (deprecated). "
            "Rename to .meridian/kb/ to upgrade."
        )
        return (fs_dir, True)
    
    # Neither exists — return kb path (will be created on first use)
    return (kb_dir, False)
```

### Behavior Matrix

| fs/ exists | kb/ exists | Result |
|------------|------------|--------|
| ✗ | ✗ | Use `kb/`, create on first use |
| ✗ | ✓ | Use `kb/` |
| ✓ | ✗ | Use `fs/` (legacy fallback), warn |
| ✓ | ✓ | Use `kb/`, warn about orphaned `fs/` |

### Environment Variable Alias

```python
def _normalize_meridian_kb_dir(env: dict[str, str]) -> None:
    # Check for new name first
    explicit_kb = env.get("MERIDIAN_KB_DIR", "").strip()
    if explicit_kb:
        env["MERIDIAN_KB_DIR"] = explicit_kb
        return
    
    # Fall back to deprecated name
    explicit_fs = env.get("MERIDIAN_FS_DIR", "").strip()
    if explicit_fs:
        logger.warning("MERIDIAN_FS_DIR is deprecated, use MERIDIAN_KB_DIR")
        env["MERIDIAN_KB_DIR"] = explicit_fs
        return
    
    # Resolve from config/defaults with fallback
    repo_root = env.get("MERIDIAN_REPO_ROOT", "").strip()
    if repo_root:
        kb_path, _ = resolve_kb_path_with_fallback(Path(repo_root))
        env["MERIDIAN_KB_DIR"] = kb_path.as_posix()
```

---

## Migration: v002_fs_to_kb

The `fs → kb` rename uses the existing migration framework in `migrations/`.

### Migration Entry

```toml
# registry.toml
[v002]
name = "fs_to_kb"
description = "Rename .meridian/fs/ to .meridian/kb/ (knowledge base)"
introduced = "0.1.0"
affects = ["repo"]
mode = "auto"  # auto = safe to run automatically, manual = requires explicit invocation
```

### Migration Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `auto` | Runs automatically on detection during startup | Safe, non-destructive, reversible |
| `manual` | User must run `meridian migrate run vNNN` | Destructive, complex, or needs confirmation |

The `fs → kb` migration is `auto` because:
- It's a simple rename
- No data loss possible (move, not copy+delete)
- Safe when `kb/` doesn't exist
- Falls back gracefully if migration fails

### Detection + Auto-Migration Flow

```python
# During state initialization
def ensure_state_initialized(repo_root: Path) -> None:
    # Run auto-migrations
    run_auto_migrations(repo_root)
    
    # Then normal init
    ensure_gitignore(repo_root)

def run_auto_migrations(repo_root: Path) -> None:
    """Run all pending auto-mode migrations."""
    for migration in get_pending_migrations(repo_root):
        if migration.mode == "auto":
            result = migration.run(repo_root)
            if result["status"] == "ok":
                logger.info(f"Auto-migrated: {migration.id}")
```

### Migration Implementation

```
migrations/v002_fs_to_kb/
├── check.py
├── migrate.py
└── README.md
```

**check.py:**
```python
def check(repo_root: Path) -> dict:
    meridian_dir = repo_root / ".meridian"
    fs_dir = meridian_dir / "fs"
    kb_dir = meridian_dir / "kb"
    
    if not fs_dir.exists():
        return {"status": "not_applicable", "reason": "No .meridian/fs/"}
    
    if kb_dir.exists():
        return {"status": "not_applicable", "reason": "Both fs/ and kb/ exist — manual resolution needed"}
    
    tracking = _read_tracking(meridian_dir)
    if "v002" in tracking.get("applied", []):
        return {"status": "done", "reason": "Already applied"}
    
    return {"status": "needed", "reason": ".meridian/fs/ exists, .meridian/kb/ does not"}
```

**migrate.py:**
```python
def migrate(repo_root: Path) -> dict:
    status = check(repo_root)
    if status["status"] != "needed":
        return status
    
    meridian_dir = repo_root / ".meridian"
    fs_dir = meridian_dir / "fs"
    kb_dir = meridian_dir / "kb"
    
    # Atomic rename
    fs_dir.rename(kb_dir)
    
    # Update .gitignore
    _update_gitignore(meridian_dir)
    
    # Track migration
    _update_tracking(meridian_dir / ".migrations.json", "v002")
    
    return {"status": "ok", "migrated": ["fs/ → kb/"], "message": "Renamed .meridian/fs/ to .meridian/kb/"}

def _update_gitignore(meridian_dir: Path) -> None:
    gitignore = meridian_dir / ".gitignore"
    if not gitignore.exists():
        return
    content = gitignore.read_text()
    updated = content.replace("!fs/", "!kb/").replace("!fs/**", "!kb/**")
    if updated != content:
        atomic_write_text(gitignore, updated)
```

### Fallback When Auto-Migration Fails

If auto-migration can't run (e.g., both `fs/` and `kb/` exist), the system:
1. Logs a warning with resolution guidance
2. Uses `kb/` if it exists, else falls back to `fs/`
3. Continues operation — never blocks on migration failure

---

## Migration Safety Mechanics

Based on industry research across Alembic, Flyway, Prisma, Terraform, and other migration systems.

### Two-Phase Migration

All migrations follow a two-phase commit pattern:

```
Phase 1: Stage
├── Create .migration-staging/ directory
├── Write intent.json with migration_id
├── Transform data to staged location
└── Validate staged data

Phase 2: Commit (only if Phase 1 succeeds)
├── Atomic moves from staging to final locations
├── Update .migrations.json tracking
└── Remove .migration-staging/
```

### Pre-Migration Backup

Before mutating, create a backup manifest:

```python
# .meridian/.migration-backup/v002_fs_to_kb/
manifest.json      # checksums and paths
fs/                # copy of original fs/ directory
```

The backup allows:
- Rollback if migration fails mid-way
- Manual recovery if crash leaves inconsistent state
- Audit trail of what was changed

### Crash Recovery

On startup, detect incomplete migrations:

```python
def detect_incomplete_migration(repo_root: Path) -> str | None:
    staging = repo_root / ".meridian" / ".migration-staging"
    if staging.exists():
        intent = staging / "intent.json"
        if intent.exists():
            return json.loads(intent.read_text())["migration_id"]
    return None
```

Recovery behavior:
- Auto-migrations: re-run automatically (idempotent)
- Manual-migrations: prompt user with `meridian migrate doctor`

### Atomic Operations

All file writes use the atomic pattern:

```python
def atomic_rename(old: Path, new: Path) -> None:
    """Atomic directory rename via POSIX rename()."""
    # On POSIX, rename() is atomic if same filesystem
    old.rename(new)

def atomic_write(path: Path, content: bytes) -> None:
    """Atomic file write via tmp + fsync + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(content)
    os.fsync(tmp.open().fileno())
    tmp.rename(path)
```

### UX During Pending Migration

| Command type | Behavior when migration pending |
|--------------|--------------------------------|
| Write ops (`spawn`, `sync`, `work start`) | Block with clear error + remediation command |
| Read ops (`status`, `show`, `context`) | Allow for diagnosis |
| Migrate ops (`migrate run`, `migrate doctor`) | Always available |

Error message format:
```
Error: Migration v002_fs_to_kb pending.

Detected: .meridian/fs/ (deprecated)
Action:   Run 'meridian migrate run v002' to upgrade
          Or:  'meridian migrate plan v002' to preview changes

Read commands (status, show) still work.
```

---

## Migration Command (Revised)

### Command Signature

```bash
meridian context migrate <name> <destination>
```

### Behavior

1. Resolve current path for `<name>` from config (or default)
2. Move contents to `<destination>`
3. Update `meridian.local.toml` with new path
4. Done — no git operations

### Implementation

```python
def migrate_context(name: str, destination: Path) -> None:
    """Move context to new location and update config."""
    
    # 1. Get current resolved path
    current = resolve_context_path(name)
    
    # 2. Check destination
    if destination.exists() and _has_content(destination):
        raise ContextMigrationError(f"Destination not empty: {destination}")
    
    # 3. Move contents
    destination.mkdir(parents=True, exist_ok=True)
    for item in current.iterdir():
        shutil.move(str(item), str(destination / item.name))
    current.rmdir()
    
    # 4. Update config (path only, not source)
    _update_local_config(name, path=str(destination))

def _has_content(path: Path) -> bool:
    """Check if directory has content (ignoring metadata)."""
    IGNORED = {".git", ".DS_Store", ".gitkeep", ".gitignore"}
    for item in path.iterdir():
        if item.name not in IGNORED:
            return True
    return False
```

### Example Flows

```bash
# Externalize work to private location
$ meridian context migrate work ~/private/work
Moved: .meridian/work → ~/private/work
Updated: meridian.local.toml

# Then optionally set up git (user does this)
$ cd ~/private/work
$ git init
$ git remote add origin git@github.com:me/ctx.git
$ git add . && git commit -m "initial" && git push

# Then enable git sync (user edits config)
# [context.work]
# source = "git"
# path = "~/private/work"
```

---

## Git Sync Warning System

### Warning Scenarios

| Condition | When Checked | Warning |
|-----------|--------------|---------|
| `source = "git"` but no `.git/` | Session start | "Not a git repository, sync disabled" |
| No remote configured | On pull/push attempt | "No remote configured, skipping" |
| Network error | On pull/push attempt | "Network error, skipping" |
| Auth failure | On pull/push attempt | "Authentication failed, skipping" |

### Implementation

```python
def check_git_repo_status(context_dir: Path, context_name: str) -> GitStatus:
    """Check git repo status and return warnings if any."""
    
    if not (context_dir / ".git").exists():
        return GitStatus(
            valid=False,
            warning=f"context.{context_name} has source = git but {context_dir} is not a git repository. "
                    f"Git sync disabled. To fix: run 'git init' in {context_dir}"
        )
    
    # Check for remote
    result = subprocess.run(
        ["git", "remote"],
        cwd=context_dir,
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        return GitStatus(
            valid=True,
            has_remote=False,
            warning=f"context.{context_name} has no git remote. Push/pull will be skipped. "
                    f"To fix: run 'git remote add origin <url>' in {context_dir}"
        )
    
    return GitStatus(valid=True, has_remote=True)
```

### Warning Output

Warnings go to stderr, don't block operations:

```
$ meridian spawn ...
Warning: context.work has source = git but ~/private/work is not a git repository.
         Git sync disabled. To fix: run 'git init' in ~/private/work
[spawn continues normally]
```

---

## Product Model (Obsidian-Inspired)

### Core Principle

Contexts are just folders. Meridian reads and writes files. How the folder syncs is the user's choice.

### Sync Options (User Perspective)

| Option | Setup | Maintenance | Best For |
|--------|-------|-------------|----------|
| **Local only** | None | None | Single machine |
| **Cloud folder** | Put in Dropbox/iCloud/OneDrive | None | Easy cross-machine |
| **Git sync** | `git init` + remote + config | Meridian handles | Version history |
| **Meridian Sync** | One click (future) | None | Just works |

### README Messaging

> **Sync your context however you want.**
> 
> By default, context lives in `.meridian/work/` and `.meridian/kb/`. To sync across machines:
> 
> - **Easy**: Put the folder in Dropbox, iCloud, OneDrive, or Google Drive
> - **Power user**: Point to a git repo with `source = "git"` for auto push/pull
> - **Coming soon**: Meridian Sync — zero-config managed sync
