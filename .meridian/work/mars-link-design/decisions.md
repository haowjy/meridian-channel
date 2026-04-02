# Decisions Log

## D1: TARGET is a name, not a path

**Context**: Init's positional arg had a dot-prefix heuristic (`path_str.starts_with('.')`) to distinguish target dirs from project roots. This misclassified `./my-project` and `.hidden-project/`.

**Decision**: TARGET is a simple directory name (no `/` allowed). Path-based init uses `--root`.

**Alternatives rejected**:
- Keep heuristic but fix edge cases — fragile, every new case needs a rule
- Remove positional arg entirely, always use `--root` — poor ergonomics for the common case

**Evidence**: Every CLI tool surveyed (git init, cargo init, uv init) treats the path arg as "init IN this directory" with no heuristic disambiguation.

## D2: Separate WELL_KNOWN and TOOL_DIRS

**Context**: WELL_KNOWN was local to `find_agents_root`. Reviewer p665 recommended extracting to module-level shared constant. Question: should `.cursor` and `.claude` be in WELL_KNOWN?

**Decision**: Two separate constants. WELL_KNOWN = `[".agents"]` (mars's conventional root). TOOL_DIRS = `[".claude", ".cursor"]` (tool directories that commonly need linking). Root detection searches both.

**Alternatives rejected**:
- Single `KNOWN_DIRS` array — loses the semantic distinction. Init uses WELL_KNOWN for defaults, link uses TOOL_DIRS for warnings. Merging them removes useful information.
- Configurable via agents.toml — over-engineering for v1. Can add later if needed.

## D3: Lightweight mutate_config instead of full sync pipeline for link mutations

**Context**: Reviewer p665 flagged that `persist_link()` bypasses sync.lock. Options: route through `sync::execute` with a `mutation_only` flag, or extract a lightweight function.

**Decision**: Extract `sync::mutate_config(root, mutation)` — acquires sync.lock, loads config, applies mutation, saves. Reuses `ConfigMutation` enum and `apply_mutation` function.

**Alternatives rejected**:
- Full sync pipeline with `mutation_only: true` — adds a flag to SyncOptions that only link uses, couples link to the full pipeline's validation stages, and runs unnecessary code (resolve, fetch, diff)
- Direct load/save with manual lock acquisition in link.rs — duplicates the lock pattern, doesn't use ConfigMutation enum

## D4: Scan-then-act for conflict resolution

**Context**: Need to handle existing files in target dirs. Question: scan all then act, or scan-and-act per file?

**Decision**: Scan ALL subdirs and files first, then act only if zero conflicts. The entire link operation is all-or-nothing at the scan boundary.

**Alternatives rejected**:
- Per-file scan-and-act — partial state on conflict (some files moved, some not). Harder to reason about, harder to recover from.
- Backup-and-restore — additional complexity, temp dir management, still has partial state during restore if that fails

## D5: Init idempotency — no-op + proceed with --link

**Context**: Current init errors when agents.toml already exists. But `mars init --link .claude` should work on an existing project.

**Decision**: If already initialized, print info and proceed with `--link` flags. Init itself is idempotent; linking is the useful action on re-runs.

**Alternatives rejected**:
- Always error — forces users to run `mars link` separately, making `--link` useless on established projects
- Re-initialize (overwrite) — destroys existing config

## D7: Hold sync.lock for entire link operation (post-review)

**Context**: Reviewers p668, p669, and p667 all flagged that scan-then-act without locking allows race conditions — a concurrent `mars sync` could create files in the managed root between scan and act, and `rename()` would overwrite them.

**Decision**: Hold `.mars/sync.lock` for the entire link operation: scan + act + config persist. This is the simplest correct approach and matches the sync pipeline's pattern of holding the lock start-to-end.

**Alternatives rejected**:
- Lock only during act phase — scan results could be stale
- Per-file revalidation before move — complex, doesn't protect against all races
- No locking (document acceptable races) — violates the project's crash-only design principle

## D8: Type-safe LinkMutation instead of generic mutate_config (post-review)

**Context**: Reviewer p667 flagged that `mutate_config(&ConfigMutation)` accepts any variant, allowing callers to accidentally bypass the full sync pipeline for mutations that need it.

**Decision**: Separate `LinkMutation` enum with only `Set`/`Clear` variants. Compile-time enforcement that only link operations use the lightweight path.

## D9: Copy+delete instead of rename for merge (post-review)

**Context**: Reviewer p668 flagged that `rename()` fails with `EXDEV` across filesystems, and the "idempotent re-run" claim doesn't hold for repeatable failures.

**Decision**: Use `copy + remove_file` instead of `rename`. Works across filesystems. The scan phase already verified safety, so destination either doesn't exist or has identical content.

## D10: Strict canonicalize comparison (post-review)

**Context**: Reviewers p668 and p667 both flagged that `canonicalize().ok() == canonicalize().ok()` treats two failures as equal — a broken foreign symlink would be removed if the expected path is also inaccessible.

**Decision**: Only match when both sides canonicalize successfully. `(Ok(a), Ok(b)) => a == b`, anything else → false.

## D11: Non-regular file entries treated as conflicts (post-review)

**Context**: Reviewers p668 and p667 flagged that symlinks and special files inside target dirs have no defined handling. `remove_dir_all` after scanning only files would destroy them silently.

**Decision**: During scan, any entry that is not a regular file and not a directory is treated as a conflict. Empty directories are ignored during scan and cleaned up bottom-up during act (using `remove_dir`, not `remove_dir_all`).

## D6: Unlink verifies symlink target before removing

**Context**: Current unlink removes any symlink without checking what it points to.

**Decision**: Only remove symlinks that resolve to THIS mars root (via canonicalize comparison). Warn and skip symlinks pointing elsewhere.

**Rationale**: Prevents accidentally breaking symlinks managed by a different tool or a different mars installation. The user can always use `rm` directly if they need to force-remove.
