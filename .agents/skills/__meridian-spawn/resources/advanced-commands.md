# Advanced Spawn Commands

Read this when you need continue, cancel, stats, permissions, reports, or dry-run — commands beyond the core loop. For troubleshooting, read `debugging.md`.

## Continue & Fork

Resume a previous spawn's harness session, or fork it to try an alternate approach:

```bash
meridian spawn --continue SPAWN_ID -p "Follow up instruction"
meridian spawn --continue SPAWN_ID --fork -p "Try alternate approach"
```

`--continue` reuses the harness session (conversation history preserved) — use it for follow-ups where you want the agent to build on what it already did. `--fork` branches from the same session but creates a new spawn ID — use it when you want to explore an alternative direction while preserving the original trajectory as a fallback.

## Cancel

```bash
meridian spawn cancel SPAWN_ID
```

Sends SIGINT to the harness process. The spawn finalizes with exit code 130.

## Stats

Check cost, token usage, and duration across spawns — useful for tracking budget, comparing model costs, or identifying spawns that took unexpectedly long:

```bash
meridian spawn stats
meridian spawn stats --session ID
```

Use `--session` to scope to a specific coordination session.

## Spawn Show Flags

```bash
meridian spawn show SPAWN_ID --no-report     # omit the full report text
meridian spawn show SPAWN_ID --include-files  # include file metadata
```

## Reports

Foreground `spawn` and `spawn wait` return status only. Use `spawn show` (report included by default) or `spawn report` subcommands for report management:

```bash
# View status + report together
meridian spawn show SPAWN_ID

# View a spawn's report
meridian spawn report show --spawn SPAWN_ID

# Search across all spawn reports by text
meridian spawn report search "auth refactor" --limit 10

# Create or update a report externally (e.g., orchestrator annotating a spawn)
meridian spawn report create "Summary of findings..." --spawn SPAWN_ID

# Pipe report content from stdin
echo "Report content" | meridian spawn report create --spawn SPAWN_ID --stdin
```

## Inspecting a Spawn's Conversation

Read what a spawn said and did using `meridian session log` with the spawn ID:

```bash
meridian session log p107              # last 5 messages
meridian session log p107 --last 20    # more history
meridian session search "error" p107   # search for specific text
```

This reads the spawn's own transcript. Combine with `spawn children` to trace a full spawn tree:

```bash
meridian spawn children p107           # discover child IDs
meridian session log p108              # read a child's conversation
```

## Dry Run

```bash
meridian spawn --dry-run -m MODEL -p "Plan the migration"
```

Preview the assembled prompt and command without executing the harness.

## Permission Tiers

Use `--sandbox` to control filesystem access and `--approval` to control tool approval behavior:

```bash
meridian spawn -m MODEL -p "Read-only analysis" --sandbox read-only
meridian spawn -m MODEL -p "Careful run" --approval confirm
```

Flags:
- `--sandbox read-only|workspace-write|unrestricted` — filesystem sandbox tier
- `--approval default|confirm|auto|yolo` — tool approval mode

## Foreground Flag (blocking)

Spawns run in the background by default. Use `--foreground` when you need the spawn to block — typically when the result feeds directly into your next action and there's nothing useful to do while waiting:

```bash
meridian spawn --foreground -a agent -p "task description"
# → blocks until complete, returns terminal status
```

This is rarely needed. The default background behavior with `spawn wait` handles most cases, including parallel spawns.

For stuck spawns, logs, or low-level state inspection, see `debugging.md`.
