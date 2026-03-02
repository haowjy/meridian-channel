---
name: meridian-run
description: Multi-agent coordination via the meridian CLI. Teaches how to spawn, track, and manage subagent runs.
---

# meridian-run

You have the `meridian` CLI for multi-agent coordination. Use it to spawn subagent runs, track progress, and inspect results.

## Run Composition

Compose each run from `model + prompt + context`:
- `model`: model id or alias
- `prompt`: task instructions
- `context`: reference files, template vars, and agent profile defaults

Start minimal, then add context only when needed.

```bash
# Basic
meridian run spawn -m MODEL -p "PROMPT"

# With reference files (repeat -f)
meridian run spawn -m MODEL -p "Implement fix" \
  -f plans/step.md \
  -f src/module.py

# With an agent profile
meridian run spawn -a reviewer -m MODEL -p "Review this change"

# With template vars (use {{KEY}} in prompt, no spaces)
meridian run spawn -m MODEL \
  -p "Implement {{TASK}} with {{CONSTRAINT}}" \
  --prompt-var TASK=auth-refactor \
  --prompt-var CONSTRAINT=no-db

# Dry-run preview (no execution)
meridian run spawn --dry-run -m MODEL -p "Plan the migration"
```

## Key Flags (`meridian run spawn`)

| Flag | Purpose | Notes |
| --- | --- | --- |
| `--model`, `-m` | Select model id or alias | Optional if agent/defaults provide one |
| `--prompt`, `-p` | Prompt text | Primary run instructions |
| `--file`, `-f` | Add reference files | Repeatable |
| `--agent`, `-a` | Use an agent profile | Applies profile model/skills/sandbox defaults |
| `--prompt-var` | Template vars (`KEY=VALUE`) | Repeatable; replaces `{{KEY}}` |
| `--background` | Return immediately with run id | Use with `meridian run wait` |
| `--dry-run` | Preview composed run | No harness execution |
| `--timeout-secs` | Runtime timeout | Float seconds |
| `--permission` | Override permission tier | Example: `read-only`, `workspace-write` |
| `--report-path` | Relative report output path | Default `report.md` |

## Parallel Execution

Launch independent runs in the background, then wait for all:
```bash
R1=$(meridian run spawn --background -m MODEL -p "Step A")
R2=$(meridian run spawn --background -m MODEL -p "Step B")
meridian run wait $R1 $R2
```

## Run Inspection

```bash
# List runs
meridian run list
meridian run list --failed
meridian run list --model MODEL
meridian run list --status STATUS

# Inspect one run
meridian run show RUN_ID
meridian run show RUN_ID --report
meridian run show RUN_ID --include-files

# Wait for completion
meridian run wait RUN_ID
meridian run wait RUN_ID --report

# Continue an existing run
meridian run continue RUN_ID -p "Follow up instruction"
meridian run continue RUN_ID -p "Try alternate approach" --fork

# Aggregate stats
meridian run stats
meridian run stats --session ID
```

## Model Selection

Use model discovery commands before spawning runs:

```bash
meridian models list
meridian models show MODEL
```

The CLI routes each model to the correct harness automatically.
