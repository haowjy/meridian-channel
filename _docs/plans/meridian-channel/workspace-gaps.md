# Workspace Gaps

**Status:** draft

Bugs and missing features in the workspace system.

---

## 1. `meridian hooks` command group — hook handlers in Python

**Problem:** Hook logic currently lives in shell scripts (`.orchestrate/hooks/scripts/`), which are part of the orchestrate plugin and not meridian-channel. Meridian-channel should own its own hook handlers so session tracking, compaction re-injection, and other workspace lifecycle concerns live in the Python CLI.

**Design:** Hooks are thin entry points — the `.claude/settings.json` (or equivalent for other harnesses) calls `uv run meridian hooks <event>`, and all logic lives in Python.

Hook configuration (committed to repo in `.claude/settings.json` or distributed via plugin):
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "uv run meridian hooks session-start" }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          { "type": "command", "command": "uv run meridian hooks session-end" }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          { "type": "command", "command": "uv run meridian hooks pre-compact" }
        ]
      }
    ]
  }
}
```

**Hook protocol:** Each handler reads JSON from stdin (hook payload with `session_id`, `source`, `cwd`, `transcript_path`, etc.) and writes JSON to stdout (`{ "additionalContext": "..." }` for context injection, or `{}` for no-op).

**`meridian hooks` subcommands:**

| Command | Trigger | Responsibility |
|---------|---------|---------------|
| `session-track` | `SessionStart` (all), `SessionEnd` | Write session ID to workspace session log |
| `context-reinject` | `SessionStart` (compact, clear) | Re-inject skills + pinned files |

**`session-track`:**
- Reads `session_id` from hook stdin JSON
- Reads `MERIDIAN_WORKSPACE_ID` from env (if set)
- Appends `{"session_id", "timestamp"}` to workspace session log
- Dedup at read time (same session ID may appear multiple times across compact/clear events)
- Fires on every `SessionStart` (startup, compact, clear) and `SessionEnd`
- Skipped when `MERIDIAN_DEPTH > 0` — child run sessions are tracked via run finalization, not hooks

**`context-reinject`:**
- Only fires on compact/clear (not startup — skills are already in context)
- Two sources of context to re-inject:
  1. **Skills:** Reads `MERIDIAN_RUN_ID` from env → looks up run's skills from SQLite. No transcript scanning needed — we know exactly what skills were launched because we stored them at run creation.
  2. **Pinned files:** Reads `MERIDIAN_WORKSPACE_ID` from env → loads pinned files via workspace context. Only applies if run is within a workspace.
- Returns `{"additionalContext": "<skill content + pinned file content>"}` so the harness injects it into the session
- For clear: follow the existing pattern — only re-inject if the previous session ended with plan acceptance (ExitPlanMode). Manual `/clear` is intentional reset.

**Requires:**
- `MERIDIAN_RUN_ID` env var set on all runs (supervisor and child). Currently not set — needs to be added to both `launch_supervisor()` and `spawn_and_stream()`.
- Supervisor needs to be tracked as a run in the database so its skills are queryable.

**Files to create:**
- `src/meridian/cli/hooks.py` — CLI command group
- `src/meridian/lib/ops/hooks.py` — hook handler logic

**Codex limitation:** Codex has no hooks, so skills and pinned files cannot be re-injected after compaction on long Codex runs. This applies to both interactive `codex` and non-interactive `codex exec`. Gap resolves when Codex adds hook support.

---

## 2. No explicit session tracking on resume

**Problem:** `workspace resume` launches the supervisor harness without passing an explicit session ID to continue. It relies on the harness implicitly continuing the last session in the working directory. The `supervisor_harness_session_id` column exists in the schema but is never populated.

**Impact:** If a workspace had multiple supervisor sessions (e.g., from crashes or `--fresh` starts), there's no way to pick a specific one. The harness just continues whatever it thinks is latest.

**Per-harness continuation mechanisms:**

| Harness | Continue flag | Session ID source |
|---------|--------------|-------------------|
| Claude | `--continue <session_id>` | Session files in working directory |
| Codex | `codex exec resume <session_id>` | Session files managed by codex |
| OpenCode | `opencode run --continue <session_id>` | Session/thread IDs from output |

Always use explicit session IDs — never rely on implicit "last session" behavior.

**Note:** Session IDs change — compaction, clear, and auto-accept plan edits each start a new session in Claude. So we need to track the *latest* session ID, not just the initial one.

**Fix:** The `meridian hooks session-start` handler (#1) writes session events to a workspace session log on every session change (startup, compact, clear). `session-end` writes the close event.

Session log at `.meridian/active-workspaces/<workspace_id>.sessions.jsonl`:
```jsonl
{"session_id": "abc123", "source": "startup", "timestamp": "...", "harness": "claude"}
{"session_id": "abc123", "source": "compact", "timestamp": "..."}
{"session_id": "def456", "source": "startup", "timestamp": "..."}
{"session_id": "def456", "source": "end", "timestamp": "..."}
```

Then:
- `meridian workspace resume` reads the session log to get the latest session ID
- Passes harness-specific continue flag: `--continue <session_id>` (Claude), `codex exec resume <session_id>` (Codex), etc.
- Each adapter needs a `continue_flags(session_id: str) -> list[str]` method
- `meridian workspace sessions [workspace]` — list all sessions with status (active/ended)
- `meridian workspace resume [workspace] --session <session_id>` — resume a specific session (default: most recent)

**Depends on:** #1 (hook handlers write the session log)

**Codex limitation:** Codex has no hooks. Interactive Codex supervisor sessions won't have real-time session tracking. Child runs via `codex exec` still capture session IDs via finalization. This gap resolves when Codex adds hook support.

---

## 3. Compaction re-injection

**Problem:** When a harness compacts/summarizes its conversation, skill instructions and pinned file contents get lossy-compressed.

**Fix:** Handled by `meridian hooks session-start` (#1). When `source` is `compact`, the handler:
1. Loads the active skills for the workspace (from agent profile + explicit skills)
2. Loads pinned files via `meridian context list`
3. Returns `{ "additionalContext": "<skills + pinned files>" }` so the harness re-injects them

This replaces the current shell-based approach in `.orchestrate/hooks/scripts/session-start.sh`.

**Depends on:** #1 (hook handlers)

**Codex limitation:** No hooks, so skills and pinned files cannot be re-injected after compaction on long Codex runs. This applies to both interactive `codex` and non-interactive `codex exec`. Gap resolves when Codex adds hook support.

---

## 4. Resume re-injects pinned context unnecessarily

~~**Problem:** `workspace resume` calls `inject_pinned_context()` and stuffs pinned file contents into the prompt, even on non-fresh resume where `--continue` means the conversation already has the full history.~~

**Status:** Fixed — pinned context is now only injected on `fresh=True` starts.

---

## 5. Workspace summary re-generated on every resume

**Problem:** `workspace resume` calls `generate_workspace_summary()` every time, even on non-fresh resume where it's not injected into the prompt. Unnecessary work.

**Investigate:** Is the summary generation cheap enough to not matter? Or should it be skipped on non-fresh resume?
