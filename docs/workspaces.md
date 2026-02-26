# Workspaces

Workspaces are persistent sessions that scope runs, pin context files, and maintain a summary across conversation compactions. They're optional — `meridian run` works standalone.

## Lifecycle

```
                    ┌──────────┐
         start ──>  │  active  │
                    └────┬─────┘
                    pause│  ▲ resume
                    ┌────▼─────┐
                    │  paused  │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              ▼                     ▼
        ┌───────────┐        ┌───────────┐
        │ completed │        │ abandoned │
        └───────────┘        └───────────┘
```

**State transitions:**
- `active` → `paused` (normal exit, Ctrl-C, SIGTERM)
- `active` → `abandoned` (harness crash, non-zero exit)
- `active` → `completed` (explicit close)
- `paused` → `active` (resume)
- `paused` → `completed` (explicit close)
- `paused` → `abandoned` (explicit close)
- `completed` and `abandoned` are terminal — no further transitions.

## Starting a Workspace

```bash
meridian start --name auth-refactor
```

This:
1. Creates a workspace row in SQLite with state `active`
2. Generates `workspace-summary.md` at `.meridian/workspaces/<id>/`
3. Writes a lock file at `.meridian/active-workspaces/<id>.lock`
4. Sets environment variables for the child process:
   - `MERIDIAN_WORKSPACE_ID=<id>`
   - `MERIDIAN_DEPTH=0`
   - `MERIDIAN_WORKSPACE_PROMPT=<composed prompt>`
5. Spawns the supervisor harness (Claude CLI by default)
6. Waits for the harness to exit
7. Transitions to `paused` or `abandoned` based on exit code
8. Cleans up the lock file

The supervisor receives a composed prompt with workspace context, pinned files, and instructions for using meridian tools.

## Resuming a Workspace

```bash
meridian workspace resume              # latest active/paused workspace
meridian workspace resume --workspace w3
meridian workspace resume --fresh      # no continuation guidance
```

Resume:
1. Resolves the target workspace (explicit ID, or most recent active, then paused)
2. Regenerates `workspace-summary.md` with latest run data
3. Loads all pinned context files
4. Composes a new supervisor prompt with:
   - Workspace summary
   - Pinned file contents
   - Continuation guidance (unless `--fresh`)
5. Launches a new supervisor conversation

`--fresh` starts a clean conversation but still includes pinned context and the workspace summary. Use it when the previous conversation's context is stale or unhelpful.

## Context Pinning

Pin files to a workspace so they survive conversation compaction:

```bash
meridian context pin docs/architecture.md
meridian context pin spec.md
meridian context list
meridian context unpin spec.md
```

Pinned files are:
- Stored in SQLite (file path + workspace ID)
- Logged as workflow events (`ContextPinned`, `ContextUnpinned`)
- Re-injected into the supervisor prompt on every resume
- Formatted as `# Pinned Context: <relative_path>` blocks

`workspace-summary.md` is **always implicitly pinned** and cannot be unpinned.

If a pinned file is missing at resume time, the resume fails with a `FileNotFoundError`. Either restore the file or unpin it.

## Workspace Summary

Generated at `.meridian/workspaces/<id>/workspace-summary.md`, the summary contains:
- Workspace metadata (ID, name, state, created date)
- List of pinned files
- Recent runs with status, model, duration, and report excerpts

The summary is regenerated on every `start` and `resume`, ensuring the supervisor always has current context.

## Runs Inside Workspaces

When `MERIDIAN_WORKSPACE_ID` is set, all `meridian run` commands are automatically scoped to that workspace:

```bash
# Inside a workspace session:
meridian run create -p "Research the problem"    # creates w1/r1
meridian run create -p "Implement the fix"       # creates w1/r2
meridian list                                     # shows only w1's runs
```

Run IDs inside workspaces are prefixed: `w1/r1`, `w1/r2`, etc.

## Exporting Artifacts

Export committable markdown from a workspace:

```bash
meridian export workspace --workspace w1
```

This gathers:
- `workspace-summary.md`
- Run report files (`report.md`)
- Pinned markdown files

## Lock Files

Active workspaces write a lock file at `.meridian/active-workspaces/<id>.lock` containing the supervisor PID. This prevents concurrent supervisors on the same workspace.

If meridian is killed ungracefully (SIGKILL, OOM), the lock file may be left behind. `meridian diag repair` detects stale locks and cleans them up, also transitioning stuck-active workspaces to `abandoned`.

## Environment Variables

| Variable | Set By | Purpose |
|----------|--------|---------|
| `MERIDIAN_WORKSPACE_ID` | `workspace start/resume` | Auto-scope runs to workspace |
| `MERIDIAN_DEPTH` | workspace launch | Current agent nesting depth (starts at 0) |
| `MERIDIAN_MAX_DEPTH` | user/config | Max nesting depth (default 3) |
| `MERIDIAN_WORKSPACE_PROMPT` | workspace launch | Full supervisor prompt |
| `MERIDIAN_SUPERVISOR_COMMAND` | user | Override supervisor binary (for testing) |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | `--autocompact` | Claude autocompact threshold |
