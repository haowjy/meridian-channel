# Decision Log

## D1: Canonicalize comparison — match on (Ok, Ok) only

**Context:** F4 found that `canonicalize().ok() == canonicalize().ok()` treats two failures as equal.

**Decision:** Use `match (resolved.canonicalize(), expected.canonicalize())` and only return true on `(Ok(a), Ok(b)) if a == b`. All other cases (any Err) return false.

**Alternatives rejected:**
- *Compare raw paths when canonicalize fails* — raw paths may have `.`, `..`, or symlinks, making textual comparison unreliable.
- *Return error when canonicalize fails* — too strict. The managed subdir may legitimately not exist yet (empty `agents/` not created). Treating failure as "not matching" is correct — if we can't confirm they're the same, they're not confirmed the same.

**Note:** `scan_link_target()` in link.rs already uses the correct pattern. `unlink()` was fixed in a prior commit. Only `check_link_health()` in doctor.rs still has the bug.

## D2: Sync reorder vs journaling for crash safety

**Context:** F12 found that saving config before apply makes crashes non-recoverable.

**Decision:** Move config save to after apply+lock, relying on sync idempotency for crash recovery.

**Alternatives rejected:**
- *Journaled approach (write intent file, apply, commit)* — the sync pipeline is already idempotent. The only thing breaking idempotency is saving the config mutation early (so re-running doesn't replay the mutation). Moving the save late restores natural idempotency without adding new infrastructure.
- *Two-phase commit (save config as pending, apply, promote to final)* — more complex, requires a new "pending config" concept, and the recovery logic is harder to reason about than "just re-run the command."

## D3: Rename-old pattern for atomic_install_dir vs. copy-on-write

**Context:** F13 found a gap between `remove_dir_all(dest)` and `rename(tmp, dest)`.

**Decision:** Rename dest to `.old`, rename new into place, then delete `.old`. Rollback on failure.

**Alternatives rejected:**
- *Copy-on-write / reflink* — requires filesystem support (btrfs/APFS), not portable.
- *Keep both old and new, swap via rename* — same as chosen approach, just different naming. We use `.{name}.old` prefix to keep it hidden.
- *Accept the gap since sync.lock is held* — true that another mars process can't race, but a crash still leaves the dir missing. Sync lock doesn't protect against crashes.

## D4: Skip symlinks in scanning rather than follow with depth limit

**Context:** F3 found that check/doctor follow symlinks to arbitrary locations.

**Decision:** Skip symlinked entries with a warning. Do not follow them.

**Alternatives rejected:**
- *Follow with depth/size limit* — complicated to implement correctly. What's the right limit? What if the symlink points to a valid skill that happens to be large? The limit becomes a heuristic, violating AGENTS.md principle 4.
- *Resolve and validate the target* — still follows the symlink, which is the core risk. A symlink to `/dev/random` would hang regardless of validation.
- *Error on symlinks* — too strict. Users may have legitimate reasons for symlinks (dev overrides). Warning + skip is informative without blocking.

## D5: Containment check only for auto-discovered roots

**Context:** F1 found that symlinked `.agents/` can redirect project_root.

**Decision:** Validate containment in `find_agents_root()` for auto-discovered roots only. `--root` bypasses the check.

**Alternatives rejected:**
- *Always validate, including --root* — `--root` is explicitly "I know what I'm doing." Blocking it breaks legitimate cross-project operations.
- *Never canonicalize managed_root* — breaks symlink comparison in link.rs (relative vs absolute paths don't match).
- *Store both canonical and original paths* — adds complexity throughout the codebase for a rare edge case. The containment check at the boundary is simpler.

## D6: Per-entry flock for git cache vs content-addressed entries

**Context:** F14 found that git clone cache entries can race across processes.

**Decision:** Use `FileLock` per cache entry (`{url_dirname}.lock`) around fetch+checkout.

**Alternatives rejected:**
- *Content-addressed git entries (`{url}_{sha}/`)* — requires full repo copy per version, breaks shallow clone optimization, wastes disk.
- *Global cache lock* — too coarse. Different URLs should be fetchable concurrently.
- *Accept the race* — corruption risk is real when two repos share a git source. The lock is cheap insurance.

## D7: Tier 3 deferred — extract shared scanning after symlink work

**Context:** F19/F20 are refactoring findings with no correctness impact.

**Decision:** Defer to backlog. If/when F3 symlink scanning is implemented, extract shared infrastructure at that time.

**Reasoning:** The scanning code will change during F3 implementation. Refactoring before F3 means doing the work twice. Refactoring after F3 captures both the structural improvement and the symlink-awareness in one pass.
