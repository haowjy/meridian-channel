# Phase 4: Implement `_ensure_claude_session_accessible()` Symlink

## Scope

Implement the symlink function that makes Claude sessions accessible across CWD boundaries, and wire it into both launch sites (child spawns in runner.py, primary launches in process.py). This is the phase that actually fixes the "No conversation found" bug.

## Files to Modify

### `src/meridian/lib/launch/runner.py`

#### 1. Add `_ensure_claude_session_accessible()` function

Import the public `project_slug()` from Phase 1b:

```python
from meridian.lib.harness.claude import project_slug
```

Add the symlink function:

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

    Uses project_slug() from claude.py for path encoding -- must stay
    in sync with Claude Code's actual project directory naming.
    """
    if source_cwd is None:
        return  # can't determine source project dir
    if source_cwd.resolve() == child_cwd.resolve():
        return  # same project dir, no symlink needed

    claude_projects = Path.home() / ".claude" / "projects"
    source_slug = project_slug(source_cwd)
    child_slug = project_slug(child_cwd)

    source_file = claude_projects / source_slug / f"{source_session_id}.jsonl"
    if not source_file.exists():
        return  # source session not found, let Claude handle the error

    child_project = claude_projects / child_slug
    child_project.mkdir(parents=True, exist_ok=True)
    target_file = child_project / f"{source_session_id}.jsonl"
    try:
        os.symlink(source_file, target_file)
    except FileExistsError:
        pass  # another process already created it -- fine
```

Note: `project_slug()` was renamed from `_project_slug()` in Phase 1b. It implements `str(path.resolve()).replace("/", "-")` -- the exact encoding Claude Code uses.

#### 2. Wire into `execute_with_finalization()`

After the CWD flip block and the Phase 2a `update_spawn` call, before the `while True:` retry loop:

```python
# Symlink source session into child's project dir so Claude can find it.
if (
    harness.id == HarnessId.CLAUDE
    and plan.session.harness_session_id
    and plan.session.source_execution_cwd
):
    _ensure_claude_session_accessible(
        source_session_id=plan.session.harness_session_id,
        source_cwd=Path(plan.session.source_execution_cwd),
        child_cwd=child_cwd,
    )
```

### `src/meridian/lib/launch/process.py`

#### 1. Import the symlink function

```python
from meridian.lib.launch.runner import _ensure_claude_session_accessible
```

Or, to avoid cross-module private import, either:
- Make it public: `ensure_claude_session_accessible` (remove underscore in runner.py)
- Move it to a shared helper: `launch/session_compat.py`
- Duplicate the 20-line function

**Recommended**: Make it public in runner.py (`ensure_claude_session_accessible`). It's a legitimate cross-module API.

#### 2. Wire into `run_harness_process()`

Before `_run_primary_process_with_capture()` (line 376):

```python
# Symlink source session for primary fork launches (e.g., meridian --fork p452).
if (
    plan.adapter.id == HarnessId.CLAUDE
    and plan.source_execution_cwd
    and resolved_harness_session_id
):
    ensure_claude_session_accessible(
        source_session_id=resolved_harness_session_id,
        source_cwd=Path(plan.source_execution_cwd),
        child_cwd=repo_root,
    )
```

For primary launches, `child_cwd` is `repo_root` (primary processes always run from repo root).

## Dependencies

- **Requires**: Phase 3 (`source_execution_cwd` threaded through DTOs to reach call sites), Phase 1b (`project_slug()` is public)
- **Produces**: Working session symlinks. The fork/resume bug is fixed.
- **Independent of**: Phase 1e (Codex fix).

## Interface Contract

```python
def ensure_claude_session_accessible(
    source_session_id: str,
    source_cwd: Path | None,   # CWD where source session was created
    child_cwd: Path,            # CWD where the new process will run
) -> None
```

## Constraints

- **Path encoding MUST match Claude Code's**: Use `project_slug()` from `claude.py` (Phase 1b). This implements `str(path.resolve()).replace("/", "-")`. Do NOT use `re.sub(r'[^a-zA-Z0-9]', '-', ...)` -- it produces different output.
- **Symlink creation MUST be idempotent**: Use `try: os.symlink() except FileExistsError: pass`. NOT check-then-act. Two concurrent spawns forking from the same source could race.
- **Only symlink the `.jsonl` file**: Claude uses the JSONL for session lookup. Subagent dirs are not needed for MVP.
- **Only for Claude harness**: Skip for Codex, OpenCode, etc. Guard with `harness.id == HarnessId.CLAUDE`.
- **No cleanup needed**: Symlinks in ephemeral project dirs are harmless and tiny.
- Handle gracefully: `source_cwd is None` (return), same CWD (no symlink), missing source file (return).

## How It Flows

### Fork-from-child (spawn path):

1. Spawn p452 ran with `child_cwd = .meridian/spawns/p452/log/`
2. `execution_cwd` recorded on p452's spawn record AND session record (Phase 2a)
3. Session created at `~/.claude/projects/-home-...-spawns-p452-log/UUID.jsonl`
4. Later: `meridian spawn --fork p452` resolves reference, gets `source_execution_cwd` (Phase 3)
5. Fork spawn runs with its own `child_cwd = .meridian/spawns/p471/log/`
6. Before launch: symlink UUID.jsonl from p452's project dir -> p471's project dir
7. `claude --resume UUID --fork-session` finds the session via symlink

### Fork-from-chat-ref (primary path):

1. Child spawn created session c5 with `execution_cwd = .meridian/spawns/p452/log/`
2. Later: `meridian --fork c5` resolves reference, gets `source_execution_cwd`
3. Primary launch runs with CWD = repo_root (different from source)
4. Before launch: symlink UUID.jsonl from p452's project dir -> repo root's project dir
5. `claude --resume UUID --fork-session` finds the session via symlink

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] `ensure_claude_session_accessible` function exists and handles: source_cwd=None, same CWD, missing source file, FileExistsError race
- [ ] runner.py calls `ensure_claude_session_accessible` after CWD flip, before command execution
- [ ] process.py calls `ensure_claude_session_accessible` before `_run_primary_process_with_capture()`
- [ ] Both call sites gate on `HarnessId.CLAUDE` and non-None source values
- [ ] Path encoding uses `project_slug()` from claude.py
- [ ] Symlink is created with `os.symlink` + `FileExistsError` catch (not check-then-act)
