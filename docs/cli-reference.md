# CLI Reference

## Global Options

These flags work with any command and must appear before the subcommand:

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON (equivalent to `--format json`) |
| `--porcelain` | Machine-readable key=value output |
| `--format <mode>` | Output mode: `rich` (default TTY), `plain` (default non-TTY), `json`, `porcelain` |
| `--yes` | Auto-confirm all prompts |
| `--no-input` | Fail on any interactive prompt (CI mode) |
| `--version` | Print version and exit |

Output auto-detection: when stdout is a TTY, output defaults to `rich` (colored, formatted). Non-TTY defaults to `plain` (no ANSI, no box-drawing). `--json` and `--porcelain` always disable rich formatting.

---

## `meridian run`

Manage agent runs.

### `meridian run create`

Create and execute a run. Blocks until completion in CLI mode.

```bash
meridian run create -p "Implement the feature" -m gpt-5.3-codex
meridian run create -p "Review changes" -m claude-opus-4-6 -s review
meridian run create -p "Research approaches" -f plan.md -f spec.md --dry-run
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--prompt` | `-p` | string | `""` | Task prompt |
| `--model` | `-m` | string | auto | Model ID or alias (e.g., `opus`, `codex`, `sonnet`) |
| `--skills` | `-s` | string[] | `()` | Skills to compose into prompt |
| `--file` | `-f` | path[] | `()` | Reference files appended to prompt |
| `--var` | | KEY=VALUE[] | `()` | Template variables for `${KEY}` substitution |
| `--agent` | | string | none | Agent profile name (loads from `.agents/agents/`) |
| `--report-path` | | string | `report.md` | Output report filename |
| `--dry-run` | | bool | false | Preview composed prompt and command without executing |
| `--workspace` | | string | auto | Workspace ID (auto-detected from `MERIDIAN_WORKSPACE_ID`) |
| `--timeout-secs` | | float | none | Kill run after N seconds |
| `--permission` | | string | `read-only` | Permission tier (see [Safety](safety.md)) |
| `--unsafe` | | bool | false | Required for `danger` permission tier |
| `--budget-usd` | | float | none | Per-run cost limit in USD |
| `--budget-per-workspace-usd` | | float | none | Workspace cumulative cost limit |
| `--guardrail` | | path[] | `()` | Post-run validation scripts |
| `--secret` | | KEY=VALUE[] | `()` | Secrets redacted from all output |

**Aliases:** `meridian run -p "..."` works as shorthand for `meridian run create -p "..."`.

### `meridian run list`

List runs with optional filters.

```bash
meridian list                           # latest 20 runs
meridian run list --failed              # only failed runs
meridian run list --workspace w1        # runs in workspace
meridian run list --status running      # filter by status
meridian run list --model codex --limit 5
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--workspace` | string | none | Filter by workspace ID |
| `--status` | string | none | Filter: `queued`, `running`, `succeeded`, `failed`, `cancelled` |
| `--model` | string | none | Filter by model |
| `--limit` | int | 20 | Max results |
| `--no-workspace` | bool | false | Only standalone (non-workspace) runs |
| `--failed` | bool | false | Shorthand for `--status failed` |

### `meridian run show <run_id>`

Show details of a specific run.

```bash
meridian show r1                        # basic details
meridian show r1 --include-report       # with full report text
meridian show r1 --include-files        # with files-touched list
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--include-report` | bool | false | Include full report markdown |
| `--include-files` | bool | false | Include list of files touched |

### `meridian run continue <run_id>`

Continue a previous run with a follow-up prompt. Creates a new run linked to the original.

```bash
meridian run continue r1 -p "Also fix the edge case in line 42"
meridian run continue r1 -p "Try a different approach" -m claude-opus-4-6
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--prompt` | `-p` | string | required | Follow-up prompt |
| `--model` | `-m` | string | original | Override model |
| `--timeout-secs` | | float | none | Timeout |

### `meridian run retry <run_id>`

Retry a failed run. Uses the original prompt unless overridden.

```bash
meridian run retry r3                   # same prompt, same model
meridian run retry r3 -p "Try with more context" -m opus
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--prompt` | `-p` | string | original | Override prompt |
| `--model` | `-m` | string | original | Override model |
| `--timeout-secs` | | float | none | Timeout |

### `meridian run wait <run_id>`

Block until a run reaches a terminal status. Useful after MCP's non-blocking `run_create`.

```bash
meridian wait r1
meridian wait r1 --timeout-secs 300 --include-report
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--timeout-secs` | float | 600 | Max wait time |
| `--include-report` | bool | false | Include report when done |
| `--include-files` | bool | false | Include files-touched when done |

---

## `meridian workspace`

Manage persistent workspaces.

### `meridian workspace start`

Create a workspace and launch a supervisor harness. The `meridian` process stays alive as the parent, managing the workspace lifecycle.

```bash
meridian start                                  # auto-named workspace
meridian start --name auth-refactor             # named workspace
meridian start --model claude-opus-4-6          # specify supervisor model
meridian start --autocompact 80                 # set compaction threshold
meridian start -- --verbose                     # passthrough args to harness
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--name` | string | auto-generated | Workspace name |
| `--model` | string | default | Supervisor model |
| `--autocompact` | int | none | Claude autocompact percentage threshold |
| `--harness-arg` | string[] | `()` | Extra args forwarded to harness CLI |

**What happens:**
1. Creates workspace row in SQLite
2. Generates `workspace-summary.md`
3. Writes lock file (`.meridian/active-workspaces/<id>.lock`)
4. Sets `MERIDIAN_WORKSPACE_ID` in child environment
5. Spawns supervisor harness, waits for exit
6. On exit: transitions to `paused` (normal) or `abandoned` (crash)
7. Cleans up lock file

### `meridian workspace resume`

Resume a paused workspace. Regenerates the summary, re-injects pinned context, and launches a new supervisor conversation.

```bash
meridian workspace resume                       # latest active/paused workspace
meridian workspace resume --workspace w3        # specific workspace
meridian workspace resume --fresh               # new conversation, no history
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--workspace` | string | auto | Workspace ID (defaults to most recent active, then paused) |
| `--fresh` | bool | false | Start fresh conversation (still includes pinned context) |
| `--model` | string | default | Override supervisor model |
| `--autocompact` | int | none | Autocompact threshold |
| `--harness-arg` | string[] | `()` | Passthrough args |

### `meridian workspace list`

```bash
meridian workspace list
meridian workspace list --limit 5
```

### `meridian workspace show <workspace_id>`

Show workspace details, including state, run count, and pinned files.

### `meridian workspace close <workspace_id>`

Transition workspace to `completed` state.

---

## `meridian skills`

Discover and inspect skills from `.agents/skills/`.

### `meridian skills list`

List all indexed skills with name, description, and tags.

### `meridian skills search <query>`

Search skills by keyword or tag.

```bash
meridian skills search "review"
meridian skills search "testing"
```

### `meridian skills show <name>`

Load and display the full SKILL.md content.

```bash
meridian skills show review
meridian skills show scratchpad
```

### `meridian skills reindex`

Rebuild the skill index from `.agents/skills/`. Run after adding or modifying skills.

---

## `meridian models`

Browse the model catalog.

### `meridian models list`

List all available models with routing info and cost tier.

### `meridian models show <name>`

Show details for a specific model by ID or alias.

```bash
meridian models show opus
meridian models show gpt-5.3-codex
```

---

## `meridian context`

Pin files to workspace context. Pinned files survive conversation compaction and are re-injected on resume.

### `meridian context pin <file_path>`

```bash
meridian context pin docs/architecture.md
meridian context pin --workspace w1 plan.md
```

### `meridian context unpin <file_path>`

```bash
meridian context unpin plan.md
```

Note: `workspace-summary.md` is always implicitly pinned and cannot be unpinned.

### `meridian context list`

```bash
meridian context list
meridian context list --workspace w1
```

---

## `meridian diag`

Diagnostics and repair.

### `meridian diag doctor`

Run health checks: schema version, run/workspace counts, directory structure.

```bash
meridian doctor          # alias
meridian diag doctor
```

### `meridian diag repair`

Fix common issues:
- Remove stale workspace lock files
- Repair missing schema tables
- Rebuild corrupt JSONL from SQLite
- Transition stuck-active workspaces to abandoned
- Run WAL checkpoint

```bash
meridian diag repair
```

---

## `meridian export`

Export workspace artifacts for committing to version control.

### `meridian export workspace`

Gather committable markdown artifacts: workspace summary, run reports, pinned markdown files.

```bash
meridian export
meridian export workspace --workspace w1
```

---

## `meridian migrate`

Migrate from legacy bash-based run-agent tooling.

### `meridian migrate run`

Import `runs.jsonl` into SQLite, rename skill directories, and update references.

```bash
meridian migrate run
meridian migrate run --repo-root /path/to/repo
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--jsonl-path` | string | auto | Path to legacy `runs.jsonl` |
| `--apply-skill-migrations` | bool | true | Rename skill dirs and update references |
| `--repo-root` | string | `.` | Repository root |

Migration is idempotent — safe to run multiple times.

---

## `meridian serve`

Start the MCP server on stdio. Used by MCP-aware agents (Claude, etc.) to call meridian tools programmatically.

```bash
meridian serve
```

---

## `meridian completion`

Shell completion helpers.

```bash
meridian completion bash       # print bash completion script
meridian completion zsh        # print zsh completion script
meridian completion fish       # print fish completion script
meridian completion install    # auto-install to shell config
```

---

## Top-Level Aliases

| Alias | Equivalent |
|-------|------------|
| `meridian start [args]` | `meridian workspace start [args]` |
| `meridian list` | `meridian run list` |
| `meridian show [id]` | `meridian run show [id]` |
| `meridian wait [id]` | `meridian run wait [id]` |
| `meridian doctor` | `meridian diag doctor` |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Agent/harness error |
| 2 | Infrastructure error (spawn failure, missing binary) |
| 3 | Timeout |
| 130 | SIGINT (Ctrl-C) |
| 143 | SIGTERM |
