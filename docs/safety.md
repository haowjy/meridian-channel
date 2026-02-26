# Safety

meridian provides four layers of safety: permission tiers, cost budgets, guardrail scripts, and secret redaction.

## Permission Tiers

Permission tiers control what the agent harness can do. The default is `read-only`.

```bash
meridian run create -p "Read the code" --permission read-only       # default
meridian run create -p "Edit files" --permission workspace-write
meridian run create -p "Run anything" --permission full-access
meridian run create -p "Skip all checks" --permission danger --unsafe
```

| Tier | What it allows | Claude CLI flags | Codex CLI flags |
|------|---------------|------------------|-----------------|
| `read-only` | Read files, search, git log/status/diff | `--allowedTools Read,Glob,Grep,Bash(git status)...` | `--sandbox read-only` |
| `workspace-write` | + Edit, Write, git add, git commit | Adds `Edit,Write,Bash(git add),Bash(git commit)` | `--sandbox workspace-write` |
| `full-access` | + Web access, unrestricted Bash | Adds `WebFetch,WebSearch,Bash` | `--sandbox danger-full-access` |
| `danger` | Skip all safety checks | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` |

The `danger` tier requires the `--unsafe` flag as a deliberate opt-in. Without it, the command fails immediately.

### Agent Profile Permissions

Agent profiles (`.agents/agents/*.md`) can set a default permission level via the `sandbox` frontmatter field:

```yaml
---
name: reviewer
sandbox: read-only
skills: [review]
---
```

Mapping: `read-only` → `read-only`, `workspace-write` → `workspace-write`, `danger-full-access` → `full-access`, `unrestricted` → `full-access`.

CLI `--permission` flag overrides the agent profile default.

## Cost Budgets

Set spending limits per-run and per-workspace.

```bash
# Per-run limit
meridian run create -p "..." --budget-usd 2.00

# Per-workspace limit (cumulative across all runs)
meridian run create -p "..." --budget-per-workspace-usd 10.00

# Both
meridian run create -p "..." --budget-usd 2.00 --budget-per-workspace-usd 10.00
```

### How budgets work

1. **Pre-flight check**: Before starting, verify workspace cumulative spend is under the limit
2. **Streaming monitor**: During execution, parse harness stdout for cost JSON fields in real-time
3. **On breach**: Send SIGTERM to the harness, escalate to SIGKILL after grace period
4. **Post-run check**: Verify extracted usage against budget after process exits
5. **Workflow event**: `budget_exceeded` event emitted on breach

The streaming monitor looks for JSON fields: `total_cost_usd`, `cost_usd`, `cost`, `total_cost`, `totalCostUsd` in harness stdout.

## Guardrail Scripts

Post-run validation scripts that can trigger automatic retries.

```bash
meridian run create -p "..." --guardrail ./checks/lint.sh --guardrail ./checks/tests.sh
```

### How guardrails work

1. After each run attempt completes, guardrail scripts run in order
2. Each script receives environment variables:
   - `MERIDIAN_GUARDRAIL_RUN_ID` — the run ID
   - `MERIDIAN_GUARDRAIL_OUTPUT_LOG` — path to `output.jsonl`
   - `MERIDIAN_GUARDRAIL_REPORT_PATH` — path to `report.md`
3. Exit code 0 = pass, non-zero = fail
4. On failure: the run is automatically retried (up to 3 attempts)
5. Each script has a 30-second timeout
6. Scripts do NOT receive `MERIDIAN_SECRET_*` environment variables (stripped for security)

### Example guardrail script

```bash
#!/bin/bash
# checks/lint.sh — fail if linter finds issues
cd meridian-channel && uv run ruff check .
```

## Secret Redaction

Prevent sensitive values from appearing in any output, logs, or artifacts.

```bash
meridian run create -p "Deploy to staging" \
  --secret API_KEY=sk-abc123 \
  --secret DB_PASSWORD=hunter2
```

### How redaction works

1. Secret values are passed to the child harness as `MERIDIAN_SECRET_<KEY>` environment variables
2. All stdout and stderr output is redacted **before** writing to disk:
   - `sk-abc123` → `[REDACTED:API_KEY]`
   - `hunter2` → `[REDACTED:DB_PASSWORD]`
3. Report files (`report.md`) are also redacted after extraction
4. Longer secrets are replaced first to prevent partial matches
5. Guardrail scripts do NOT receive secret env vars

### What's protected

| Location | Redacted? |
|----------|-----------|
| `output.jsonl` | Yes (redacted before write) |
| `stderr.log` | Yes (redacted before write) |
| `report.md` | Yes (redacted after extraction) |
| Child process env | Secrets available as `MERIDIAN_SECRET_*` |
| Guardrail script env | No (secrets stripped) |
| SQLite `runs.db` | Prompts stored as-is (don't put secrets in prompts) |

## Depth Limiting

Prevents runaway agent recursion when agents spawn sub-agents.

```
MERIDIAN_DEPTH=0 → meridian run create (sets DEPTH=1 for child)
  └─ MERIDIAN_DEPTH=1 → meridian run create (sets DEPTH=2 for child)
       └─ MERIDIAN_DEPTH=2 → meridian run create (sets DEPTH=3 for child)
            └─ MERIDIAN_DEPTH=3 → REFUSED: "Max agent depth (3) reached"
```

- `MERIDIAN_DEPTH` is auto-incremented on each `meridian run`
- `MERIDIAN_MAX_DEPTH` (default 3) sets the ceiling
- At max depth: returns a structured error telling the agent to complete the task directly
- Workspace `start` resets depth to 0
