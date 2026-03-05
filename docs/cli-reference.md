# CLI Reference

Current CLI surface from `meridian --help`.

## Top-Level Commands

```text
completion  config  doctor  init  models  report  serve  skills  space  spawn
```

## Global Options

Use before subcommands:

| Flag | Description |
|---|---|
| `--json` | JSON output |
| `--porcelain` | Stable key/value output |
| `--format text\|json\|porcelain` | Explicit output format |
| `--config <path>` | Load user config overlay |
| `--yes` | Auto-confirm prompts where supported |
| `--no-input` | Fail instead of prompting |
| `--version` | Print version |

## Primary Launch (`meridian`)

`meridian` with no subcommand launches the primary harness session.

```bash
meridian [--new] [--space SPACE_ID] [--continue SESSION_REF] \
  [--model MODEL] [--harness HARNESS] [--agent AGENT] \
  [--permission TIER] [--unsafe] [--autocompact N] [--dry-run]
```

Examples:

```bash
# default: latest active space, else create one
meridian

# force new space + fresh session
meridian --new

# fresh session in explicit existing space
meridian --space s12

# continue by harness session ref
meridian --continue sess_abc123
```

### `--continue` Resolution

Resolution order and behavior:

1. If `SESSION_REF` matches tracked history, Meridian uses that mapped space/session.
2. If `--space` is supplied and conflicts with a tracked mapping, Meridian warns and uses the tracked space.
3. If `SESSION_REF` is unknown and not a chat alias (`cN`), Meridian treats it as a harness session id and binds it to:
   - `--space <id>` when provided, otherwise
   - default-selected space (latest active, else new).
4. Chat aliases (`cN`) must already exist; unknown aliases error.

Warnings are emitted in both text and JSON output (`warning` field).

### Primary Output Contract

- Non-dry-run:
  - no full command echo
  - includes resume hint when available:
    - `Resume this session with:`
    - `meridian --continue <continue_ref>`
- Dry-run:
  - includes fully resolved command
- JSON:
  - includes `space_id`, `continue_ref`, `resume_command`, `warning`
  - `command` is populated for dry-run only

## `meridian spawn`

Create and manage spawns.

### `spawn` / `spawn create`

```bash
meridian spawn -p "Implement feature" -m gpt-5.3-codex
meridian spawn create --background -p "Long task" -m gpt-5.3-codex
meridian spawn create --dry-run -p "Plan only"
```

Common flags:

| Flag | Notes |
|---|---|
| `--prompt, -p` | Prompt text |
| `--prompt-var` | Repeatable `KEY=VALUE` vars for `{{KEY}}` |
| `--model, -m` | Model id or alias |
| `--file, -f` | Repeatable reference files |
| `--agent, -a` | Agent profile name |
| `--report-path` | Relative report path (default `report.md`) |
| `--dry-run` | Compose only, do not execute harness |
| `--background` | Return immediately with spawn ID (`p*`) |
| `--space-id`, `--space` | Explicit space scope |
| `--timeout` | Runtime limit in minutes |
| `--permission` | Permission tier |

### `spawn list`

```bash
meridian spawn list
meridian spawn list --space s12 --status failed
```

### `spawn show`

```bash
meridian spawn show p7
meridian spawn show p7 --report --include-files
```

`spawn_id` also accepts references: `@latest`, `@last-failed`, `@last-completed`.

### `spawn continue`

```bash
meridian spawn continue p7 -p "Add tests"
meridian spawn continue p7 -p "Try alternative" --fork
```

### `spawn wait`

```bash
meridian spawn wait p7
meridian spawn wait p7 p8 --report
```

### `spawn stats`

```bash
meridian spawn stats
meridian spawn stats --space s12 --session c4
```

## `meridian report`

Create and query spawn-scoped reports.

### `report` / `report create`

```bash
meridian report create "Summary markdown..." --spawn p7
printf "# Report\n\nDone.\n" | meridian report create --stdin --spawn p7
```

Defaults:
- If `--spawn` is omitted, `report create` resolves the current spawn from `MERIDIAN_SPAWN_ID`.

### `report show`

```bash
meridian report show --spawn p7
meridian report show --spawn @latest
```

### `report search`

```bash
meridian report search "guardrail" --space s12
meridian report search "timeout" --spawn @last-failed
```

## `meridian space`

### `space start`

```bash
meridian space start --name auth-refactor
meridian space start --model claude-opus-4-6 --autocompact 70
```

### `space resume`

```bash
meridian space resume
meridian space resume --space s12 --fresh
```

### `space list/show/close`

```bash
meridian space list --limit 20
meridian space show s12
meridian space close s12
```

## Other Commands

```bash
meridian config init
meridian skills list
meridian models list
meridian doctor
meridian serve
```
