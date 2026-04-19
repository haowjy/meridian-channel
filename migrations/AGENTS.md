# Migrations — Agent Instructions

## Key Principles

1. **Never import migrations from runtime code.** Migrations import from `meridian.*`, never the reverse. The main codebase must work without the migrations directory.

2. **Migrations are standalone scripts.** Each can run via `python migrations/vNNN_name/migrate.py /path/to/repo`. No framework dependencies beyond what Meridian itself needs.

3. **Check before mutating.** Every migration must detect if it's already been applied and no-op gracefully.

4. **Track both locations.** Some migrations affect repo state (`.meridian/`), some affect user state (`~/.meridian/projects/<uuid>/`), some affect both. Update tracking in the appropriate location(s).

5. **Two-phase commit.** Stage transformed data first, validate, then commit the migration marker only after all writes succeed. Never mark complete before data is safe.

6. **Atomic writes always.** Use `tmp + fsync + rename` pattern for every file written. Never write directly to the target path.

---

## Auto vs Manual Migrations

Migrations declare a `mode` in `registry.toml`:

| Mode | When to use | Behavior |
|------|-------------|----------|
| `auto` | Deterministic, reversible, unambiguous | Runs automatically during startup |
| `manual` | Destructive, conflict-prone, needs confirmation | User must run `meridian migrate run vNNN` |

### Auto-migration criteria

Use `mode = "auto"` when ALL of these are true:
- **Deterministic** — same input always produces same output
- **Lossless** — no data loss possible
- **Unambiguous** — only one valid outcome (e.g., `fs/` exists, `kb/` doesn't → rename)
- **Local** — affects only one state root per run
- **Reversible** — can be undone or fails gracefully

### Manual-migration criteria

Use `mode = "manual"` when ANY of these are true:
- **Conflict possible** — destination exists with divergent content
- **Lossy** — fields dropped, data merged, information lost
- **Cross-scope** — moves data between project and user-global roots
- **Ambiguous** — multiple valid outcomes, needs user choice
- **Destructive** — deletes data that can't be recovered

---

## Safety Mechanics

### Pre-migration backup

Before mutating, create a backup manifest:
```python
def backup_manifest(paths: list[Path], backup_dir: Path) -> dict:
    """Copy files to backup, return manifest with checksums."""
    manifest = {"backed_up_at": datetime.now().isoformat(), "files": []}
    for path in paths:
        if path.exists():
            dest = backup_dir / path.name
            shutil.copy2(path, dest)
            manifest["files"].append({
                "original": str(path),
                "backup": str(dest),
                "checksum": hashlib.sha256(path.read_bytes()).hexdigest()
            })
    return manifest
```

### Two-phase migration

```python
def migrate(repo_root: Path) -> dict:
    # Phase 1: Stage
    staged = stage_migration(repo_root)  # Write to .staging/
    if not validate_staged(staged):
        cleanup_staging()
        return {"status": "failed", "reason": "validation failed"}
    
    # Phase 2: Commit
    commit_staged(staged)  # Atomic moves from .staging/ to final
    update_tracking(repo_root, migration_id)
    return {"status": "ok"}
```

### Crash recovery

Detect incomplete migrations on startup:
```python
def detect_incomplete_migration(repo_root: Path) -> str | None:
    staging_dir = repo_root / ".meridian" / ".migration-staging"
    if staging_dir.exists():
        intent = staging_dir / "intent.json"
        if intent.exists():
            return json.loads(intent.read_text())["migration_id"]
    return None
```

Recovery options:
- Re-run the migration (idempotent by design)
- Roll forward from staged state
- Manual intervention with `meridian migrate doctor`

---

## Creating a New Migration

### 1. Choose a version number
Look at `registry.toml` for the next available `vNNN`. Use 3 digits, zero-padded.

### 2. Create the directory structure
```
migrations/vNNN_short_name/
  README.md      # Required: what, why, when
  check.py       # Required: detection logic
  migrate.py     # Required: transformation logic
  rollback.py    # Optional: undo logic
```

### 3. Write the check script
Must return JSON to stdout:
```json
{"status": "needed", "reason": "human-readable explanation"}
{"status": "done", "reason": "already migrated"}
{"status": "not_applicable", "reason": "fresh project, no legacy state"}
```

### 4. Write the migrate script
- Call check first, exit early if not needed
- Create backup manifest of files to be touched
- Stage transformation (write to `.migration-staging/`)
- Validate staged data
- Commit (atomic moves to final locations)
- Update `.migrations.json` tracking
- Return JSON result to stdout

### 5. Register in registry.toml
```toml
[vNNN]
name = "short_name"
description = "What this migration does"
introduced = "0.1.0"
affects = ["repo", "user"]  # Which state roots are affected
mode = "auto"               # "auto" or "manual"
```

---

## Testing Migrations

1. Create a test fixture with pre-migration state
2. Run the migration
3. Verify post-migration state
4. Run again to verify idempotency
5. Test on fresh project to verify not_applicable path
6. Test crash recovery: kill mid-migration, verify re-run succeeds
7. Test conflict scenarios for manual migrations

---

## Common Patterns

### Reading legacy state
```python
from meridian.lib.state.paths import resolve_repo_state_paths
repo_state = resolve_repo_state_paths(repo_root)
legacy_spawns = repo_state.root_dir / "spawns.jsonl"
```

### Writing to user state
```python
from meridian.lib.state.user_paths import get_project_uuid, get_project_state_root
uuid = get_project_uuid(repo_root / ".meridian")
if uuid:
    user_root = get_project_state_root(uuid)
```

### Atomic file operations
```python
from meridian.lib.state.atomic import atomic_write_text
atomic_write_text(target_path, content)
```

### Directory rename (auto-migration pattern)
```python
def migrate_rename(old: Path, new: Path) -> dict:
    if not old.exists():
        return {"status": "not_applicable"}
    if new.exists():
        return {"status": "conflict", "reason": "both paths exist"}
    
    # Atomic rename
    old.rename(new)
    return {"status": "ok", "migrated": [f"{old} → {new}"]}
```

---

## UX Guidelines

When migration is pending:
- **Block** write operations (`spawn`, `sync`) with clear error
- **Allow** read operations (`status`, `show`, `context`) for diagnosis
- Show exactly what command to run: `"Run 'meridian migrate run v002' to upgrade"`
- Show backup location if applicable

When migration fails:
- Preserve staged data for recovery
- Show `meridian migrate doctor` for diagnosis
- Never leave state in inconsistent state — either fully migrated or fully rolled back

---

## Don't

- Don't auto-run `mode = "manual"` migrations — ever
- Don't delete source data until migration is confirmed successful
- Don't assume paths exist — check and handle missing state gracefully
- Don't import from `migrations.*` anywhere in `src/meridian/`
- Don't edit applied migrations — immutable once released
- Don't write directly to target paths — always stage + atomic commit
- Don't mark migration complete before data is safe
