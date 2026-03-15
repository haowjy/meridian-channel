# Advanced Spawn Commands

Read this when you need continue, cancel, stats, permissions, template vars, or dry-run — commands outside the core spawn → wait → show loop. For troubleshooting, read `debugging.md`.

## Continue & Fork

Resume a previous spawn's harness session, or fork it to try an alternate approach:

```bash
meridian spawn --continue SPAWN_ID -p "Follow up instruction"
meridian spawn --continue SPAWN_ID --fork -p "Try alternate approach"
```

`--continue` reuses the harness session (conversation history preserved). `--fork` branches from the same session but creates a new spawn ID.

## Cancel

```bash
meridian spawn cancel SPAWN_ID
```

Sends SIGINT to the harness process. The spawn finalizes with exit code 130.

## Stats

```bash
meridian spawn stats
meridian spawn stats --session ID
```

Aggregate cost, token, and duration stats across spawns. Use `--session` to scope to a specific coordination session.

## Spawn Show Flags

```bash
meridian spawn show SPAWN_ID --no-report     # omit the full report text
meridian spawn show SPAWN_ID --include-files  # include file metadata
```

## Template Variables

```bash
meridian spawn -m MODEL \
  -p "Implement {{TASK}} with {{CONSTRAINT}}" \
  --prompt-var TASK=auth-refactor \
  --prompt-var CONSTRAINT=no-db
```

Use `{{KEY}}` placeholders in prompts, replaced at launch time.

## Dry Run

```bash
meridian spawn --dry-run -m MODEL -p "Plan the migration"
```

Preview the assembled prompt and command without executing the harness.

## Permission Tiers

Override tool access with `--permission`:

```bash
meridian spawn -m MODEL -p "Read-only analysis" --permission read-only
```

Tiers:
- `read-only` — can read files but not write or execute
- `workspace-write` — can write within the project directory
- `full-access` — unrestricted tool access

For stuck spawns, logs, or low-level state inspection, see `debugging.md`.
