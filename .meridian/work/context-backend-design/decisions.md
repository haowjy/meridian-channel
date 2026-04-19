# Context Backend Design Decisions

## DEC-CTX-001: Local Config at Project Root

**Decision**: Add `meridian.local.toml` at project root, not `.meridian/config.local.toml`.

**Reasoning**: 
- `meridian.toml` is at project root, so local override should be adjacent
- Follows the workspace.local.toml pattern but at the right level
- Cleaner than introducing a new `.meridian/config.toml` layer

**Alternatives rejected**:
- `.meridian/config.local.toml`: Would require new config file convention separate from existing `meridian.toml`
- `.meridian/config.toml` as project config: Would break existing repos using `meridian.toml` at root

---

## DEC-CTX-002: Git Sync via Subprocess

**Decision**: Use direct `git` subprocess calls, not a git library.

**Reasoning**:
- No new dependencies required
- Git CLI is universal and well-tested
- Simple operations (pull, add, commit, push) don't need library abstractions
- Easier to debug — users can reproduce commands manually

**Alternatives rejected**:
- GitPython: Adds dependency, abstracts away useful error messages
- dulwich: Pure Python but heavier than needed for simple ops

---

## DEC-CTX-003: Conflict Markers Strategy

**Decision**: On rebase conflict, commit with conflict markers and push.

**Reasoning**:
- No data loss — both sides preserved
- Explicit visibility — markers are obvious grep targets
- Manual resolution required but not blocking
- Same strategy used by many sync tools (Obsidian Sync, Syncthing)

**Alternatives rejected**:
- Abort and retry: Would lose changes
- Automatic resolution via `theirs`/`ours`: Loses data silently
- Block until resolved: Stops work

---

## DEC-CTX-004: Path Substitution Variables

**Decision**: Support `{project}` variable in path specs, expand on first use.

**Reasoning**:
- Enables single global config that works across all repos
- `~/.meridian/context/{project}/work` is natural pattern
- UUID ensures no collisions even for repos with same name

**Alternatives rejected**:
- `{repo_name}`: Collisions when multiple repos have same name
- `{repo_path_hash}`: Harder to navigate than UUID

---

## DEC-CTX-005: Non-Blocking Sync

**Decision**: Git sync failures log warnings but don't block session startup.

**Reasoning**:
- Network issues are common and transient
- Work should continue even when offline
- User can manually sync via `meridian context sync`
- Blocking makes the tool unusable on planes, trains, etc.

**Alternatives rejected**:
- Block until sync succeeds: Too fragile
- Retry loop with backoff: Delays startup, still fails eventually

---

## DEC-CTX-006: Separate Resolver Module

**Decision**: Create `src/meridian/lib/context/` module rather than extend `state/paths.py`.

**Reasoning**:
- Keeps path resolution concerns separate from state storage concerns
- Git sync logic doesn't belong in state module
- Clean import graph — context imports from state, not vice versa
- Easier to test in isolation

**Alternatives rejected**:
- Extend `paths.py`: Would conflate path resolution with git sync
- Inline in config loading: Would duplicate resolution logic

---

## DEC-CTX-007: Source Field Separates Backend from Path

**Decision**: Use `source = "local" | "git"` to specify backend type, separate from `path`.

**Reasoning**:
- Clean separation of "where" (path) from "how it syncs" (source)
- Git-specific options only valid when `source = "git"`
- Extensible to future backends (`gdrive`, `s3`, etc.)
- No magic keywords in path field — paths are just paths

**Alternatives rejected**:
- `path = "local"` magic keyword: Conflates location with backend type
- Nested `[context.work.git]`: More verbose, git options scattered

---

## DEC-CTX-008: Arbitrary Context Types Supported

**Decision**: Allow `[context.<name>]` for any name, not just `work` and `kb`.

**Reasoning**:
- Users may want `docs`, `research`, `shared` contexts
- Same config shape works for all — source + path + optional git options
- Custom contexts export as `MERIDIAN_CONTEXT_<NAME>_DIR`
- `work` and `kb` keep special env var names for compatibility

**Alternatives rejected**:
- Fixed set of `work` and `kb` only: Not extensible, forces workarounds
- Separate config file for custom contexts: Unnecessary complexity

---

## DEC-CTX-009: Rename fs to kb

**Decision**: Rename `fs` (filesystem mirror) to `kb` (knowledge base).

**Reasoning**:
- `fs` was cryptic — didn't convey meaning
- `kb` reflects the true purpose: persistent agent memory
- Contains more than just a code mirror — decision logs, design rationale, accumulated learnings
- "Knowledge base" is accurate: accumulated knowledge about the project

**Alternatives rejected**:
- `mirror`: Undersells scope — it's more than just mirroring code structure
- `codebase`: Too narrow, doesn't capture decision history and learnings
- `docs`: Conflicts with user documentation in `docs/`

---

## DEC-CTX-010: Two Built-in Contexts Always Present

**Decision**: `work` and `kb` are always present, even with zero config.

**Reasoning**:
- Both serve fundamental agent needs — ephemeral task context and persistent memory
- Zero config should "just work" with sensible defaults
- Arbitrary contexts are opt-in for users who need more

**Model**:
- `work`: Ephemeral work-item context (design, plans, decisions for current task)
- `kb`: Persistent agent memory (learnings, codebase knowledge, decision history)
- Arbitrary: User-defined, only exist when explicitly configured

**Alternatives rejected**:
- Only `work` as built-in: Leaves agent memory undefined
- All contexts opt-in: Too much config for basic usage

---

## DEC-CTX-011: Auto vs Manual Migration Modes

**Decision**: Add `mode = "auto" | "manual"` to migration registry entries.

**Reasoning**:
- Some migrations are safe to run automatically (simple renames, additive changes)
- Others need user confirmation (destructive, complex, or irreversible)
- Auto-migrations reduce friction for safe state upgrades
- Manual migrations preserve user control for risky operations

**Criteria for auto mode**:
- Non-destructive (move, not delete)
- Reversible or has clear fallback
- No user input needed
- Fails gracefully without blocking

**`v002_fs_to_kb` is auto because**:
- Simple directory rename
- Falls back to `fs/` if `kb/` already exists
- No data loss possible
- Never blocks operation on failure

**Alternatives rejected**:
- All migrations manual: Too much friction for safe upgrades
- All migrations auto: Risky for complex state transformations

---

## DEC-CTX-012: Two-Phase Migration with Staging

**Decision**: Implement two-phase commit for all migrations — stage first, then commit.

**Reasoning** (based on industry research):
- Flyway, Prisma, Alembic all use similar patterns for safety
- Staging allows validation before committing
- Crash recovery is possible by detecting incomplete staging
- Never leaves state in inconsistent state

**Pattern**:
1. Write to `.migration-staging/` with `intent.json`
2. Validate staged data
3. Atomic moves to final locations
4. Update tracking only after success

**Alternatives rejected**:
- Direct mutation: No recovery from crashes, partial state possible
- Copy-then-delete: Doubles disk usage, still risky if crash between steps

---

## DEC-CTX-013: Block Write Commands When Migration Pending

**Decision**: Manual-pending migrations block write operations but allow read operations.

**Reasoning** (based on Prisma/Terraform patterns):
- Prevents corrupted state from write operations on old schema
- Read operations still work for diagnosis
- Clear UX: exact command to run is shown
- Similar to Prisma `migrate status` blocking deploy when drift detected

**Alternatives rejected**:
- Warning-only: Risks state corruption if user ignores warning
- Block all commands: Too restrictive, can't even diagnose the issue

---

## DEC-CTX-014: Context Dependencies Are Documentation-Only (For Now)

**Decision**: Skills/agents that need custom contexts document the requirement in their README. No mars integration in this work item.

**Reasoning**:
- Keeps scope focused on context backend infrastructure
- README-based documentation is simple and works today
- Follows Homebrew `caveats` pattern — human-readable, not machine-enforced
- Future work can add mars integration (`mars doctor` warnings) if needed

**Future consideration**:
- Skills could declare `contexts: [research]` in frontmatter
- `mars sync` / `mars doctor` could warn about unconfigured contexts
- Research on npm peer deps, Terraform variables, Helm schema suggests this is valuable but not urgent

**For now**: Document context requirements in skill/agent README.

---

## DEC-CTX-015: Migrate Command Sets Path Only, Not Source

**Decision**: `meridian context migrate <name> <destination>` updates only the `path` field in config, not `source`.

**Reasoning**:
- User may not have git set up yet at destination
- Setting `source = "git"` before git init would cause immediate warnings/failures
- Decouples file movement from sync configuration
- User adds `source = "git"` when they're ready

**Alternatives rejected**:
- `--git` flag to set source: Couples two separate concerns
- Auto-detect if destination is git repo: Magic, surprising behavior

---

## DEC-CTX-016: Contextual Git Warnings, Not Upfront Checks

**Decision**: Warn about git issues when operations actually fail, not as upfront validation.

**Reasoning**:
- Simpler implementation — handle errors where they occur
- Warnings are contextual and actionable
- No wall of warnings at startup for partially-configured repos
- User sees warning when it matters (trying to sync, not just opening meridian)

**Specific warnings**:
- Session start (if `source = "git"`): "Not a git repository"
- On pull/push: "No remote configured" / "Network error" / "Auth failed"

---

## DEC-CTX-017: "Not Empty" Ignores Metadata Files

**Decision**: When checking if migration destination is empty, ignore `.git/`, `.DS_Store`, `.gitkeep`, `.gitignore`.

**Reasoning**:
- User may pre-create git repo at destination before migrating
- `.git/` existing doesn't mean there's conflicting content
- Matches user expectation: "empty" means "no content files"

---

## DEC-CTX-018: Obsidian Model — Contexts Are Just Folders

**Decision**: Position contexts as "just folders" with user-controlled sync, not managed storage.

**Reasoning**:
- Obsidian's vault model is proven and understood
- Users already know how to sync folders (Dropbox, iCloud, git)
- Reduces meridian's responsibility and maintenance burden
- Git sync is opt-in power feature, not required
- Future paid tier (Meridian Sync) fills "zero-config" need

**Implication for README**: Document that putting context folder in Dropbox/iCloud/OneDrive is a valid (easier) alternative to git sync.

---

## DEC-CTX-019: Three-Tier Sync Roadmap

**Decision**: Ship with local + git, position future paid Meridian Sync.

**Tiers**:
1. `source = "local"` (v1): Just folders, user syncs however
2. `source = "git"` (v1): Meridian automates git operations
3. `source = "meridian"` (future): Paid managed sync

**Reasoning**:
- Matches Obsidian's model (free local/git, paid Obsidian Sync)
- Git sync serves power users now
- Paid tier has clear value prop: "just works, no setup"

---

## DEC-CTX-020: Simplified v1 for Single User

**Decision**: Strip elaborate safety mechanisms, ship simple, fix forward.

**Reasoning**:
- Single user (Jimmy) — no backwards compat concerns
- Can recover manually if things break
- Faster to ship and iterate
- Add safety mechanisms when/if multi-user becomes real

**What this cuts**:
- Two-phase migration staging
- Pre-migration backup with checksums
- Crash recovery infrastructure
- Command blocking on pending migration
- Elaborate Windows path handling
- Arbitrary context type validation

**What remains**:
- Simple file move + config update
- Manual recovery documented in `v1-scope.md`
- Git sync with contextual warnings

---

## DEC-CTX-021: CLI Command is `meridian context mv`

**Decision**: Use `meridian context mv <name> <dest>` following Terraform's pattern.

**Reasoning**:
- Terraform's `state mv` is well-understood pattern
- `mv` is familiar Unix verb
- Keeps `meridian context` as the namespace (not separate `meridian mv`)
- Clear source (current resolved path) and destination

**Rejected alternatives**:
- `meridian migrate work ~/path` — confuses with versioned migrations
- `meridian mv work ~/path` — top-level command feels too generic
- `meridian context migrate` — "migrate" implies schema changes

---

## DEC-CTX-022: work-archive Deferred to Restructure

**Decision**: v1 only covers `work/` and `kb/`. `work-archive/` externalization deferred.

**Reasoning**:
- Current structure has `work/` and `work-archive/` as siblings
- Proper fix is restructure: `work/active/` + `work/archive/`
- That's a separate work item, don't block context backend on it
- Single user can manually handle archive for now

**Future work**: Restructure to `work/active/` + `work/archive/`, then single `work` externalization covers both.
