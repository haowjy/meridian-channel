# Design Spec: `--fork` as a Standalone Primitive

## Problem

Today `--fork` only works as a modifier on `--continue` in `meridian spawn`:

```bash
meridian spawn --continue p5 --fork -p "new direction"
```

This requires knowing a spawn ID, and it doesn't work on the root command at all. The real use case is simpler: "I have session c367 and want to branch off from it" — either interactively or as a spawn.

Meanwhile, `--from` (context injection) doesn't map to the root command because there's no prompt to inject into.

## Proposal

Make `--fork` a standalone flag that accepts a session or spawn reference, on both the root command and `meridian spawn`.

### CLI Surface

```bash
# Root: fork into a new interactive session
meridian --fork c367
meridian --fork p42

# Spawn: fork into a new automated spawn
meridian spawn --fork c367 -p "now do X"
meridian spawn --fork p42 -p "take a different approach"

# With overrides (fork is a new session — overrides make sense)
meridian spawn --fork c367 -m gpt -p "review with a different model"
meridian --fork c367 --agent reviewer
meridian spawn --fork p42 --yolo -p "go wild"
meridian spawn --fork p42 --work new-work-item -p "different work item"
```

`--fork <ref>` always requires a reference. No bare `--fork` flag — clean break from the old `--continue --fork` boolean modifier.

### Reference Resolution

The reference can be:
- **Session ID** (`c367`) — look up in session store, get latest harness session ID
- **Spawn ID** (`p42`) — look up in spawn store, get its harness session ID

This requires a **unified resolver** that handles both formats. Today root `--continue` only resolves harness session IDs (not meridian cNNN/pNNN refs), and spawn `--continue` only resolves spawn IDs. `--fork` needs a new shared resolver that handles both.

```python
def resolve_fork_ref(repo_root: Path, ref: str) -> ResolvedForkTarget:
    """Resolve a fork reference to a harness session ID.

    Accepts: session ID (c367), spawn ID (p42), or raw harness session ID (UUID).
    Returns: harness_session_id, harness, source_chat_id, source metadata.
    """
```

### Semantics

`--fork <ref>` means:
1. Resolve `<ref>` to a harness session ID + source metadata
2. Tell the harness to fork that conversation (native fork — full history copied, original untouched)
3. Create a **new** meridian session (`chat_id`) — never reuse the source's
4. Record fork lineage (`forked_from_chat_id`) in the session start event
5. Inherit source metadata by default (harness, agent, skills, work_id), allow overrides
6. Run the new session — either interactively (root) or with a prompt (spawn)

### Difference from `--continue`

| | `--continue` | `--fork` |
|---|---|---|
| Original session | Mutated (appended to) | Untouched |
| New session ID | No (reuses original) | Yes (new `chat_id`) |
| Conversation history | Shared (same file/DB) | Copied (independent) |
| `--model`/`--agent` | Prohibited | Allowed (default: inherit) |
| `--yolo`/`--approval` | Allowed | Allowed |
| `--work` | Inherits | Allowed (default: inherit) |
| Use case | Resume where you left off | Branch in a new direction |

### Difference from `--from`

| | `--from` | `--fork` |
|---|---|---|
| What transfers | Report summary + file list | Full conversation history |
| Fidelity | Lossy (~5% of context) | Lossless |
| Harness involvement | None (prompt injection) | Native fork mechanism |
| Works on root cmd | No (no prompt to inject) | Yes |

### Flag Interactions

| Combination | Behavior |
|---|---|
| `--fork` + `--continue` | **Error**: mutually exclusive |
| `--fork` + `--from` | **Error for MVP**: simplification, not semantic constraint. Document as such. Could be complementary in the future (fork history + inject separate context). |
| `--fork` + `--model` | Allowed: override source model |
| `--fork` + `--agent` | Allowed: override source agent (inherits source agent's skills by default) |
| `--fork` + `--yolo` | Allowed: set approval mode for new session |
| `--fork` + `--work` | Allowed: attach to different work item |
| `--fork` + `--harness` | **Error**: fork cannot cross harnesses. A Claude session can't be forked into Codex. Validate that source harness matches `--harness` if specified, or error with a clear message. |

## Harness Support

All three harnesses support native fork.

### Claude Code
```bash
claude --resume <harness_session_id> --fork-session
```
- Copies JSONL conversation file to new UUID
- Inserts `compact_boundary` marker at fork point
- `parentUuid` chain unbroken across boundary
- Already wired in `claude.py` adapter (line 254-255)
- `supports_session_fork = True` ✓

### Codex
Codex has a native `codex fork` command, but it's interactive-only — no `codex exec fork`, no `--json`, no prompt argument. Instead of using it, we implement fork ourselves by copying the rollout file and SQLite metadata.

**Codex session storage (investigated):**
```
~/.codex/state_5.sqlite          # SQLite DB with `threads` table (session index)
~/.codex/sessions/YYYY/MM/DD/    # rollout JSONL files
  rollout-<timestamp>-<uuid>.jsonl
```

**Rollout JSONL structure:**
- Line 0: `{"type": "session_meta", "payload": {"id": "<uuid>", ...}}` — session ID in ONE place
- Rest: events with independent `turn_id` UUIDs — no session ID embedded per-event

**Fork implementation (adapter-level, ~30 lines):**
1. Query `threads` table for source session's `rollout_path` and metadata
2. Generate new UUID v7
3. Copy rollout file to new path with new UUID in filename
4. Rewrite `session_meta.payload.id` in the first line to the new UUID
5. INSERT new row into `threads` table (copy metadata, new id/path/timestamps)
6. Return new UUID — pipeline then uses `codex exec resume <new_uuid> "prompt"`

This avoids the two-phase execution problem entirely. After the fork, it's just a normal resume. The adapter's `build_command()` stays single-command.

**Risks:**
- Fragile against Codex schema changes (SQLite table, JSONL format)
- `session_meta` format is fundamental — unlikely to change without a major version
- If Codex adds `codex exec fork` upstream (#11750), we can switch to it and drop the hack

**Required adapter changes:**
- Add `supports_session_fork = True` to capabilities
- Remove `FlagEffect.DROP` for `continue_fork`
- Implement `fork_session()` with the copy logic above

### OpenCode
```bash
opencode run "prompt" --session <harness_session_id> --fork
```
- SQLite DB operation — copies messages + parts with new ULIDs
- Fork is fully independent after creation (no `parent_id` link)
- Already wired in `opencode.py` adapter (line 201-202)
- `supports_session_fork = True` ✓

## Implementation

### What Already Exists

The spawn path has most of the plumbing:
- `SpawnContinueInput.fork: bool` — CLI flag on spawn
- `SpawnCreateInput.continue_fork: bool` — passed through prepare
- `SessionContinuation.continue_fork: bool` — in the plan
- `HarnessCapabilities.supports_session_fork: bool` — per adapter
- `claude.py`: appends `--fork-session` when `continue_fork=True`
- `opencode.py`: appends `--fork` when `continue_fork=True`
- `codex.py`: **not wired** — fork is a separate command, both fork-related flags are `DROP`

### What Needs to Change

#### 1. Add `forked_from_chat_id` to session event model

```python
class SessionStartEvent(BaseModel):
    # ... existing fields ...
    forked_from_chat_id: str | None = None  # Set on fork, None otherwise
```

Trivial cost, prevents permanent data loss. Can't backfill JSONL events after the fact. This is "knowledge in data, not code" per project principles.

Also add `forked_from_chat_id: str | None = None` to `SessionRecord` so consumers can read lineage.

**Threading path**: Add `forked_from_chat_id` as an optional kwarg to `start_session()`. It already takes 12+ keyword arguments — one more optional `str | None` is minimal cost. The field flows: CLI → `LaunchRequest` → `session_scope()` → `start_session()` → `SessionStartEvent`. No post-hoc update needed.

#### 2. Build a unified reference resolver

Today's resolvers are split:
- Root `--continue`: resolves harness session IDs only (not cNNN/pNNN)
- Spawn `--continue`: resolves spawn IDs only

`--fork` needs a shared resolver that handles session IDs, spawn IDs, and raw harness session IDs. Returns source metadata (harness, model, agent, skills, work_id, harness_session_id).

```python
@dataclass
class ResolvedForkTarget:
    harness_session_id: str
    harness: str
    source_chat_id: str | None  # for lineage tracking
    source_model: str
    source_agent: str | None
    source_skills: tuple[str, ...]
    source_work_id: str | None
```

**Edge cases:**
- Session with multiple `harness_session_ids` (resumed multiple times): use the latest
- Spawn with `None` harness session ID (killed before capture): error with "Spawn '{id}' has no recorded session — cannot fork"
- Raw harness session UUID: fall back to harness inference (same as `--continue` today), `source_chat_id` is `None` (no lineage)
- For session refs, metadata comes from the session record. For spawn refs, metadata comes from the spawn record.

**Metadata inheritance precedence** (for both spawn and root):
1. CLI flags (`--model`, `--agent`, `--work`) take highest priority
2. If `--agent` is overridden, its profile's skills replace inherited skills
3. If no CLI override, inherit from the resolved source metadata
4. If source has no metadata (raw UUID ref), fall back to config/profile defaults

#### 3. Decouple `--fork` from `--continue` on spawn

Change `--fork` from a boolean modifier to a standalone string flag:

```python
# spawn.py — before
continue_from: str | None   # --continue p5
fork: bool                   # --fork (requires --continue)

# spawn.py — after
continue_from: str | None    # --continue p5 (resume, mutate original)
fork_from: str | None        # --fork p5 (branch, new session)
```

No backward-compat alias for `--continue --fork`. CLAUDE.md says "no backwards compatibility needed." The old syntax was a bool that can't coexist with the new string-valued `--fork <ref>` at the parser level.

When `--fork` is provided:
- Resolve via the unified resolver
- Set `continue_fork=True` in `SpawnCreateInput`
- The rest of the pipeline is unchanged

#### 4. Add `--fork` to root command

```python
# main.py — add parameter
fork_ref: Annotated[str | None, Parameter(name="--fork", help="Fork from a session or spawn reference.")] = None
```

Wire into `_run_primary_launch`:
- Resolve reference via unified resolver
- **Critical**: do NOT pass source `chat_id` as `continue_chat_id` — that would reopen the source session. Pass `None` so a new `chat_id` is allocated, but pass `forked_from_chat_id` for lineage.
- Pass `continue_fork=True` to `LaunchRequest`
- Default to source metadata, allow `--model`/`--agent`/`--work` overrides

#### 5. Add `--fork` to harness shortcut commands

The auto-generated shortcut commands (e.g., `meridian claude`, `meridian codex`) get `--fork` for consistency.

#### 6. Add `continue_fork` to `LaunchRequest`

```python
class LaunchRequest(BaseModel):
    # ... existing fields ...
    continue_harness_session_id: str | None = None
    continue_chat_id: str | None = None
    continue_fork: bool = False  # NEW
    forked_from_chat_id: str | None = None  # NEW — lineage
```

The launch pipeline (`runner.py` → `process.py` → harness adapter) passes `continue_fork` through. Process layer must ensure a new `chat_id` is allocated (not reusing source) and the `forked_from_chat_id` is recorded in the session start event.

**Note**: `resolve_primary_launch_plan()` constructs `SpawnParams` in two places — the `MERIDIAN_HARNESS_COMMAND` override path and the normal path. Both must set `continue_fork`. The `MERIDIAN_HARNESS_COMMAND` override path **rejects `--fork`** with error: "Cannot use --fork with MERIDIAN_HARNESS_COMMAND override." This avoids complex threading through a path that bypasses normal adapter command building.

#### 6a. Fork launch mode rules

Fork is a third mode alongside "fresh" and "resume." The launch pipeline checks `bool(continue_harness_session_id)` in several places to decide behavior. For fork:

| Launch stage | Fresh | Resume | Fork |
|---|---|---|---|
| `seed_session()` | `is_resume=False` | `is_resume=True` | `is_resume=False` (new meridian session) |
| `filter_launch_content()` | Full content | Skip skills/bootstrap | Full content (new session needs skills) |
| Prompt guidance | None | `_CONTINUATION_GUIDANCE` | `_FORK_GUIDANCE` (see below) |
| `start_session()` | New `chat_id` | Reuse `chat_id` | New `chat_id` + `forked_from_chat_id` |
| `harness_session_id` | None | Source ID | Source ID (with fork flag) |

The implementation should check `continue_fork` alongside `continue_harness_session_id` at each decision point, not rely on `bool(continue_harness_session_id)` alone.

#### 6b. Fork prompt guidance

Fork is semantically *neither* a fresh start nor a continuation. The existing `_CONTINUATION_GUIDANCE` ("You are resuming an existing Meridian session...") is wrong for fork. Add fork-specific guidance:

```python
_FORK_GUIDANCE = (
    "You are working in a forked Meridian session — a branch from a prior conversation. "
    "You have the full context from the original session. The user wants to explore "
    "a different direction from here. Do not repeat completed work."
)
```

Set `pinned_context` to `_FORK_GUIDANCE` when `continue_fork=True`.

#### 6c. Skills precedence with fork

When `--fork` is combined with `--skills` or `--agent`:

1. `--fork p5` (no overrides): inherit source agent + source skills
2. `--fork p5 --skills foo,bar`: inherit source agent, **replace** inherited skills with `foo,bar`
3. `--fork p5 --agent reviewer`: use reviewer profile's model/skills, ignore source agent/skills
4. `--fork p5 --agent reviewer --skills foo,bar`: use reviewer profile, merge `foo,bar` on top (same as fresh spawn behavior)

Rule: `--agent` resets the skill set to the profile's defaults. `--skills` always overrides/extends. This matches existing spawn behavior for fresh creates — fork doesn't introduce new precedence rules.

#### 7. Wire Codex fork via file copy

Add `fork_session(source_id: str) -> str` to the adapter interface:

```python
class HarnessAdapter:
    def fork_session(self, source_session_id: str) -> str:
        """Fork a harness session, return new session ID.

        Default implementation raises NotImplementedError.
        Adapters where fork is a CLI flag (Claude, OpenCode) don't override.
        Adapters where fork requires file manipulation (Codex) override this.
        """
        raise NotImplementedError
```

**Codex implementation** (~40 lines, crash-safe):
```python
def fork_session(self, source_session_id: str) -> str:
    import sqlite3, json, tempfile, os
    from uuid import uuid4  # uuid4 is fine — Codex tolerates non-v7

    db_path = Path.home() / ".codex" / "state_5.sqlite"
    conn = sqlite3.connect(str(db_path), timeout=10)

    # 1. Look up source rollout path + metadata
    row = conn.execute(
        "SELECT rollout_path, ... FROM threads WHERE id = ?",
        (source_session_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Codex session '{source_session_id}' not found")

    # 2. Generate new UUID, determine target path
    new_id = str(uuid4())
    source_path = Path(row[0])
    new_filename = source_path.name.replace(source_session_id, new_id)
    new_path = source_path.parent / new_filename

    # 3. Stream-copy to temp file, rewriting session_meta.id on first line
    #    Crash-safe: temp file + os.replace() follows project's atomic write pattern
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=source_path.parent, suffix=".jsonl.tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w") as tmp_f, open(source_path) as src_f:
            first_line = json.loads(src_f.readline())
            first_line["payload"]["id"] = new_id
            tmp_f.write(json.dumps(first_line) + "\n")
            for line in src_f:  # stream — O(1) memory
                tmp_f.write(line)
        os.replace(tmp_path, new_path)  # atomic
    except BaseException:
        os.unlink(tmp_path)  # clean up on failure
        raise

    # 4. INSERT new thread row (after file is durable)
    conn.execute(
        "INSERT INTO threads (id, rollout_path, ...) VALUES (?, ?, ...)",
        (new_id, str(new_path), ...)
    )
    conn.commit()
    conn.close()
    return new_id
```

**Key properties:**
- Crash-safe: temp file + `os.replace()` follows project's `atomic_write_text` pattern
- Memory-efficient: streams line-by-line, not `f.read()` of entire file
- SQLite insert happens after file is durable — orphaned file without a `threads` row is harmless (Codex ignores it)
- `uuid4()` is fine — Codex doesn't require time-ordered UUIDs for session identity
- `timeout=10` on SQLite connect handles contention with running Codex instances

**Pipeline integration**: The spawn pipeline calls `fork_session()` *before* `build_command()` when `continue_fork=True` and the adapter implements it. The returned `new_id` replaces `continue_harness_session_id`, so `build_command()` just sees a normal resume. **Skip `fork_session()` when `dry_run=True`** — dry-run should preview the resume command with a placeholder, not mutate Codex state.

For Claude Code and OpenCode, `fork_session()` is not called — they handle fork via CLI flags in `build_command()` (already wired).

**Place `fork_session()` on `BaseSubprocessHarness`** (optional override, not on the Protocol). Caller checks `capabilities.supports_session_fork` before calling.

Also: add `supports_session_fork = True` to Codex capabilities and remove `FlagEffect.DROP` for `continue_fork`.

**Known limitations (MVP):**
- Orphaned Codex fork if launch fails after `fork_session()` — harmless orphaned file + row. Track for future cleanup.
- Fork of a running session may capture a partial last line (truncated JSONL). JSONL parsers tolerate this. Detect active source (check session lock) and warn: "Source session is currently running — fork captures history up to this point."

### Meridian State on Fork

When forking, meridian creates:
1. **New `chat_id`** — allocated via `reserve_chat_id()` (must NOT reuse source)
2. **New session `start` event** with:
   - `forked_from_chat_id` — lineage back to source
   - Metadata defaults from source (harness, model, agent, skills, work_id)
   - User overrides applied on top (`--model`, `--agent`, `--work`)
3. **New harness session ID** — returned by the harness after forking
4. **Lock/lease** — created fresh by `start_session()`

Spawn history is NOT copied. The fork is a clean slate on the meridian side — only conversation state (harness-level) carries over.

### User-Facing Output

**Root command** (`meridian --fork c367`):
```json
{
  "message": "Session forked.",
  "forked_from": "c367",
  "chat_id": "c402",
  "resume_command": "meridian --continue c402"
}
```

**Spawn command** (`meridian spawn --fork c367 -p "do X"`):
```json
{
  "spawn_id": "p45",
  "chat_id": "c402",
  "forked_from": "c367",
  "status": "running"
}
```

## Out of Scope (with rationale)

- **Point-in-time fork** (fork from a specific message, not HEAD) — OpenCode and Codex support this, but adds UX complexity. Can be added later with `--fork-at` syntax.
- **`--from` on root command** — doesn't make sense, as discussed. Fork covers the use case.
- **`--fork` + `--from` combined** — documented as MVP simplification, not semantic constraint. They're complementary (fork history + inject separate context) and could be combined later.

## Smoke Test Plan

```
FORK-1: meridian spawn --fork <spawn_id> -p "prompt"
  → New spawn, new chat_id, source untouched, agent gets full history
  → Verify: forked_from in session event, new chat_id != source chat_id

FORK-2: meridian --fork <session_id>
  → New interactive session, full history, original untouched
  → Verify: output shows forked_from + new chat_id + resume command

FORK-3: meridian spawn --fork <session_id> -p "prompt"
  → Same as FORK-1 but with session ref instead of spawn ref

FORK-4: meridian spawn --fork p5 --from p3
  → Error: cannot combine --fork with --from

FORK-5: meridian --fork c367 --continue c367
  → Error: cannot combine --fork with --continue

FORK-6: meridian spawn --fork p5 -m gpt -p "review"
  → Fork with model override — should use gpt, not source model

FORK-7: meridian spawn --fork p5 --agent reviewer -p "review"
  → Fork with agent override

FORK-8: meridian spawn --fork p5 --yolo -p "go"
  → Fork with yolo approval mode

FORK-9: meridian spawn --fork p5 --work other-item -p "cross-work"
  → Fork attached to different work item than source

FORK-10: Fork with each harness (claude, codex, opencode)
  → Harness-native fork invoked, new session ID captured correctly

FORK-11: Verify source session untouched after fork
  → meridian spawn show <source> unchanged, harness conversation file unchanged

FORK-12: Fork a session that doesn't exist
  → Error: clear message about invalid reference

FORK-13: Fork with harness that doesn't support it (hypothetical)
  → Error: "Harness X does not support session forking"

FORK-14: meridian --fork <ref> --dry-run
  → Preview the fork command without executing

FORK-15: meridian spawn --fork p5 --harness codex -p "cross harness"
  → Error: cannot fork across harnesses (source is claude, target is codex)

FORK-16: meridian spawn --fork p5 (where p5 has no harness session ID)
  → Error: "Spawn 'p5' has no recorded session — cannot fork"

FORK-17: meridian spawn --continue p5 --fork
  → Error: helpful message pointing to new `--fork <ref>` syntax

FORK-18: meridian spawn --fork <raw-harness-uuid> -p "prompt"
  → Works with raw UUID, no lineage (source_chat_id is None)

FORK-19: Verify fork prompt guidance
  → Forked session gets fork-specific guidance, not continuation guidance
```
