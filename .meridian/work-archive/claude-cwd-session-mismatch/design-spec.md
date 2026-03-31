# Design Spec: Fix Claude CWD/Session Lookup Mismatch

## Problem

When meridian spawns a Claude Code child process from within Claude Code (CLAUDECODE env set), the child's CWD is changed to the spawn log directory to avoid a **task output file collision** (commit `3ad11b3`). This gives the child a separate `/tmp/claude-<uid>/<encoded-cwd>/tasks/` directory so it doesn't delete the parent's active task output file during startup cleanup.

**Side effect**: Claude Code maps sessions to `~/.claude/projects/<encoded-cwd>/`. With the changed CWD, the child looks for sessions under `~/.claude/projects/<encoded-log-dir-path>/` instead of the directory where the session was originally created. This means:

- `--resume UUID --fork-session` can't find the source session → "No conversation found"
- `--continue` can't find prior sessions from the same repo
- Sessions created by the child are stored under the log dir path, not the repo path

The problem is worse when forking from a child spawn: the source session lives in `~/.claude/projects/<encoded-spawn-log-dir>/`, not in the repo root's project dir. There are currently **319** Claude project directories on this machine, many of which are spawn-specific ephemeral dirs.

This affects `--continue`, `--fork`, and any session resume operation when spawning Claude from within Claude Code.

## Root Cause

```python
# runner.py line 661-664
if os.environ.get("CLAUDECODE") and harness.id == HarnessId.CLAUDE:
    child_cwd = log_dir                    # CWD changed for task dir isolation
    child_cwd.mkdir(parents=True, exist_ok=True)
    command = (*command, "--add-dir", str(execution_cwd))
    # BUT: session lookup uses CWD, not --add-dir
```

The `--add-dir` flag grants file access but does NOT affect session lookup. Claude Code always resolves sessions from `~/.claude/projects/<encoded-cwd>/`.

## Constraints

- The task output file collision workaround MUST be preserved — Claude resume/fork still runs startup cleanup (confirmed by reviewer via Claude debug logs), so removing CWD isolation would reintroduce the original bug
- Solution must work for fresh spawns (no session to find), resume, and fork
- Must handle forking from a child spawn (session in an ephemeral project dir)
- Must handle primary `--fork pN` where pN was a child spawn (source session in ephemeral dir, primary runs from repo root)
- Must not break non-Claude harnesses
- Must not break spawns that run outside of Claude Code (CLAUDECODE not set)

## Rejected Options

### Option C: Only change CWD for non-continuation launches
**REJECTED** (reviewer finding, CRITICAL): Claude resume/fork launches still run the same startup cleanup path (`SessionStart` + `performStartupChecks`). Removing CWD isolation for resume/fork would reintroduce the task output file collision from commit `3ad11b3`.

### Option B: Use `--cwd` or `--project` to override lookup
**REJECTED**: Claude Code doesn't have `--cwd` or `--project` flags. `--session-id` creates a new session, doesn't help with lookup.

### Scanning `~/.claude/projects/*/UUID.jsonl`
**REJECTED**: 319+ project dirs and growing with every Claude spawn. Doesn't scale.

## Solution: Track execution CWD + symlink session into child project dir

### Part 1: Add `execution_cwd` to data models

Record the CWD where each harness process actually ran. This tells us which Claude project dir the session lives in.

**Both stores need it** because the reference resolver has three paths:
- `pN` → spawn store (`_resolve_spawn_reference`)
- `cN` → session store (`_resolve_chat_reference`)
- raw UUID → session store (`_resolve_harness_session_reference`)

If `execution_cwd` is only on spawn records, `--fork cN` and `--fork <raw-uuid>` on child-created Claude sessions would hit `source_cwd is None` and skip the symlink.

**Files to modify:**
- `src/meridian/lib/state/spawn_store.py` — Add `execution_cwd: str | None = None` to `SpawnRecord` and `SpawnStartEvent`
- `src/meridian/lib/state/session_store.py` — Add `execution_cwd: str | None = None` to `SessionRecord` and `SessionStartEvent`

### Part 2: Record `execution_cwd` at the right layers

**Problem**: For child spawns, `session_scope` is entered in `execute.py` (line ~696) BEFORE `runner.py` decides the actual CWD (line ~661). The session start event is emitted before the CWD flip happens. `SessionUpdateEvent` has no `execution_cwd` field today.

**Solution**: Pre-compute `execution_cwd` in `execute.py` before entering `session_scope`. The CWD flip condition is simple and stable:

```python
# In execute.py, before _session_execution_context:
execution_cwd = repo_root
if os.environ.get("CLAUDECODE") and prepared.harness_id == HarnessId.CLAUDE.value:
    execution_cwd = resolve_spawn_log_dir(repo_root, spawn_id)
```

This mirrors the condition in `runner.py` but is computed earlier so it can be passed to `session_scope` → `SessionStartEvent.execution_cwd`. The runner.py condition is a documented workaround that won't change independently.

**Recording authority by layer:**

| Layer | Records on | Value | When |
|-------|-----------|-------|------|
| `execute.py` (child spawns) | Session start event | Pre-computed `execution_cwd` | Before session_scope entry |
| `execute.py` (child spawns) | Spawn start event | Same pre-computed value | At `_init_spawn()` |
| `runner.py` (child spawns) | Spawn update event | Actual `child_cwd` after CWD decision | After CWD flip, via `spawn_store.update_spawn()` |
| `process.py` (primary launches) | Session start event | `repo_root` | At session_scope entry |
| `process.py` (primary launches) | Spawn start event | `repo_root` | At `spawn_store.start_spawn()` |

The runner.py update corrects the **spawn record** if the pre-computed value ever diverges from the actual CWD decision. Note: this cannot correct the already-written **session record**, so the pre-compute condition in execute.py must stay in sync with runner.py's CWD logic. In practice they'll match because both use the same simple condition (`CLAUDECODE` env + Claude harness). Add a code comment in both sites pointing to the other as the canonical/mirror definition.

**Files to modify:**
- `src/meridian/lib/ops/spawn/execute.py` — Pre-compute `execution_cwd`, pass to `_session_execution_context()` and `_init_spawn()`
- `src/meridian/lib/launch/runner.py` — `spawn_store.update_spawn()` with `execution_cwd=child_cwd` after CWD decision
- `src/meridian/lib/launch/process.py` — Pass `execution_cwd=repo_root` to session_scope and spawn_store.start_spawn
- `src/meridian/lib/launch/session_scope.py` — Thread `execution_cwd` parameter through to `start_session()`
- `src/meridian/lib/state/spawn_store.py` — Accept `execution_cwd` in `start_spawn()` and `update_spawn()`
- `src/meridian/lib/state/session_store.py` — Accept `execution_cwd` in `start_session()`

### Part 3: Thread `source_execution_cwd` from reference resolver to launch site

The resolved `source_execution_cwd` needs to reach the launch site where `_ensure_claude_session_accessible()` is called. The full plumbing path:

**Add `source_execution_cwd: str | None` to `ResolvedSessionReference`** — populated from all three resolver paths.

#### Spawn command path (child spawns):

```
CLI spawn.py
  → resolve_session_reference() → ResolvedSessionReference.source_execution_cwd
  → SpawnCreateInput.source_execution_cwd (new field)
  → prepare.py → SessionContinuation.source_execution_cwd (new field on plan.py)
  → PreparedSpawnPlan.session.source_execution_cwd

  Foreground: execute_spawn_foreground()
    → run_spawn() in runner.py
    → plan.session.source_execution_cwd → _ensure_claude_session_accessible()

  Background: _build_background_worker_command()
    → serialize as --source-execution-cwd <path> CLI arg
    → _background_worker_entry() deserializes
    → same path as foreground from there
```

#### Primary launch path (root `--fork`):

```
CLI main.py
  → resolve_session_reference() → ResolvedSessionReference.source_execution_cwd
  → LaunchRequest.source_execution_cwd (new field)
  → launch plan → ResolvedPrimaryLaunchPlan (carries it through)
  → process.py: _resolve_command_and_session()
  → Before _run_primary_process_with_capture(), call _ensure_claude_session_accessible()
```

Primary launches need the symlink too: `meridian --fork p452` where p452 was a child spawn. The source session lives in `~/.claude/projects/<encoded-log-dir>/` but the primary process runs from repo_root.

**Files to modify:**
- `src/meridian/lib/ops/reference.py` — Add `source_execution_cwd` to `ResolvedSessionReference`
- `src/meridian/lib/ops/spawn/models.py` — Add `source_execution_cwd` to `SpawnCreateInput`
- `src/meridian/lib/ops/spawn/plan.py` — Add `source_execution_cwd` to `SessionContinuation`
- `src/meridian/lib/ops/spawn/execute.py` — Thread through foreground path + serialize in background worker argv
- `src/meridian/lib/launch/types.py` — Add `source_execution_cwd` to `LaunchRequest`
- `src/meridian/lib/launch/process.py` — Call `_ensure_claude_session_accessible()` before primary launch
- `src/meridian/lib/launch/runner.py` — Read from `plan.session.source_execution_cwd`
- `src/meridian/cli/spawn.py` — Pass `source_execution_cwd` from resolved ref to `SpawnCreateInput`
- `src/meridian/cli/main.py` — Pass `source_execution_cwd` from resolved ref to `LaunchRequest`

### Part 4: Implement `_ensure_claude_session_accessible()` symlink

When fork/resume needs a source session and the child CWD differs from the source CWD, symlink the session file so Claude can find it.

**Path encoding**: Use the exact same encoding as the Claude adapter's `_project_slug()`: `str(path.resolve()).replace("/", "-")`. This matches actual `~/.claude/projects/` directory names on disk. Do NOT use `re.sub(r'[^a-zA-Z0-9]', '-', ...)` — that produces different output and would create symlinks in directories Claude never reads.

**Approach**: Extract `_project_slug()` from `claude.py` into a shared location (e.g., `src/meridian/lib/harness/claude.py` exports it, or move to a small `claude_compat` helper) so `runner.py` and `process.py` can call it without duplicating the encoding logic.

**Symlink creation must be idempotent**: Use `try: os.symlink(...) except FileExistsError: pass` — NOT check-then-act (`if not exists: symlink`). Two concurrent spawns forking from the same source could race.

```python
def _ensure_claude_session_accessible(
    source_session_id: str,
    source_cwd: Path | None,
    child_cwd: Path,
) -> None:
    """Symlink a Claude session file into the child's project dir.

    Claude Code maps sessions to ~/.claude/projects/<encoded-cwd>/.
    When the child runs from a different CWD than where the session was
    created, it can't find the session. This creates a symlink so both
    paths resolve.
    """
    if source_cwd is None:
        return  # can't determine source project dir
    if source_cwd.resolve() == child_cwd.resolve():
        return  # same project dir, no symlink needed

    claude_projects = Path.home() / ".claude" / "projects"
    source_slug = str(source_cwd.resolve()).replace("/", "-")
    child_slug = str(child_cwd.resolve()).replace("/", "-")

    source_file = claude_projects / source_slug / f"{source_session_id}.jsonl"
    if not source_file.exists():
        return  # source session not found, let Claude handle the error

    child_project = claude_projects / child_slug
    child_project.mkdir(parents=True, exist_ok=True)
    target_file = child_project / f"{source_session_id}.jsonl"
    try:
        os.symlink(source_file, target_file)
    except FileExistsError:
        pass  # another process already created it — fine
```

**Called from two sites:**
1. `runner.py` — for child spawns, after the CWD flip, before command execution
2. `process.py` — for primary launches, before `_run_primary_process_with_capture()`

**Note on sibling dirs**: Some Claude sessions have `<session-id>/subagents/...` directories alongside the JSONL. For MVP, we only symlink the `.jsonl` file — that's what Claude uses for `--resume`/`--fork-session` lookup. If subagent dirs are needed, we'll address it when we observe the failure.

### How it flows for fork-from-child (spawn path):

1. Spawn p452 ran with `child_cwd = .meridian/spawns/p452/log/`
2. `execution_cwd` recorded on p452's spawn record AND session record
3. Session created at `~/.claude/projects/-home-...-spawns-p452-log/UUID.jsonl`
4. Later: `meridian spawn --fork p452` resolves reference via spawn store, gets `source_execution_cwd`
5. `source_execution_cwd` flows through `SpawnCreateInput` → `SessionContinuation` → `runner.py`
6. Fork spawn runs with its own `child_cwd = .meridian/spawns/p471/log/`
7. Before launch: symlink UUID.jsonl from p452's project dir → p471's project dir
8. `claude --resume UUID --fork-session` finds the session via symlink ✓

### How it flows for fork-from-chat-ref (primary path):

1. Child spawn created session c5 with `execution_cwd = .meridian/spawns/p452/log/`
2. `execution_cwd` recorded on session record for c5
3. Later: `meridian --fork c5` resolves reference via session store, gets `source_execution_cwd`
4. `source_execution_cwd` flows through `LaunchRequest` → `process.py`
5. Primary launch runs with CWD = repo_root (different from source)
6. Before launch: symlink UUID.jsonl from p452's project dir → repo root's project dir
7. `claude --resume UUID --fork-session` finds the session via symlink ✓

### Symlink cleanup

Symlinks in ephemeral project dirs are harmless — they're tiny and Claude ignores broken symlinks. No cleanup needed for MVP. Can be cleaned up alongside the project dir proliferation issue later.

## Also fix: Codex global flag argument ordering

**Problem**: `build_harness_command()` in `common.py` always produces: `base_command + [prompt] + strategy_args + permission_flags + extra_args`. Codex's resume path puts `resume <id>` in `base_command`, so permission flags land after it. But Codex requires global flags **before** subcommands.

Affected flags from `PermissionResolver`:
- `--sandbox read-only`
- `--dangerously-bypass-approvals-and-sandbox`
- `--full-auto`
- `--ask-for-approval`

**Why `extra_args` doesn't work**: The naive fix (move `resume <id>` into `extra_args`) breaks `-o <report>` placement. Codex's `build_command()` also injects `-o report.md` into `extra_args`, so the result would be `... resume <id> -o report.md`, which may be invalid if `-o` is a global flag.

**Fix**: For the resume path, build the command directly in codex.py's `build_command()` **without delegating to `build_harness_command()`**. This gives full control over argument ordering:

```python
if harness_session_id:
    # Build resume command directly — Codex requires global flags before subcommands.
    # We cannot use build_harness_command() because its fixed output order
    # (base_command + strategies + permissions + extra_args) places permissions
    # after the resume subcommand.
    permission_flags = perms.resolve_flags(self.id)
    command: list[str] = ["codex", "exec", "--json"]
    command.extend(permission_flags)          # global flags before subcommand
    command.extend(["resume", harness_session_id])
    if run.report_output_path:
        command.extend(["-o", run.report_output_path])
    command.append("-")                       # stdin prompt
    command.extend(run.extra_args)            # passthrough args
    return command
```

Result: `codex exec --json --sandbox read-only resume <id> -o report.md - [passthrough]`

Strategy-mapped flags (model, skills, etc.) are intentionally omitted for resume — they don't apply to continuation. Apply the same pattern to the interactive resume path (`codex resume <id>`), inserting permission flags between `codex` and `resume`.

**File**: `src/meridian/lib/harness/codex.py` — Update `build_command()` for both interactive and non-interactive resume paths.

## Implementation Order

1. **Part 1**: Add `execution_cwd` to spawn store AND session store (data model changes)
2. **Part 2**: Record `execution_cwd` — pre-compute in execute.py, pass through session_scope, update in runner.py
3. **Part 3**: Thread `source_execution_cwd` from reference resolver through DTOs to launch sites
4. **Part 4**: Implement `_ensure_claude_session_accessible()` in runner.py and process.py
5. **Part 5**: Fix Codex global flag argument ordering

Parts 1→4 are sequential. Part 5 is independent (can run in parallel with any part).

## Verification

- [ ] `meridian spawn --fork <claude_spawn> -p "test"` works from within Claude Code
- [ ] `meridian spawn --fork <claude_child_spawn> -p "test"` works (fork from a child)
- [ ] `meridian spawn --continue <claude_spawn> -p "test"` works from within Claude Code
- [ ] `meridian --fork c<N>` works for a child-created Claude session (chat ref path)
- [ ] `meridian --fork <raw-uuid>` works for a child-created Claude session (UUID path)
- [ ] `meridian --fork p<N>` works for a child spawn (primary fork from child, source in ephemeral dir)
- [ ] Fresh spawns still get CWD isolation (no task file collision regression)
- [ ] Codex `resume` works with `--sandbox read-only`
- [ ] Codex `resume` works with `--full-auto`, `--ask-for-approval`, `--dangerously-bypass-approvals-and-sandbox`
- [ ] `execution_cwd` is recorded on new spawn records (child and primary)
- [ ] `execution_cwd` is recorded on new session records
- [ ] Concurrent fork-from-same-source doesn't crash (symlink race)
- [ ] Non-Claude harnesses unaffected (symlink logic skipped)
- [ ] Spawns outside CLAUDECODE unaffected (CWD = repo_root, no symlink needed)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest-llm` passes
