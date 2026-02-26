# Configuration

meridian discovers skills, agents, models, and model guidance from well-known paths relative to the repository root. No config file is required to get started — defaults work out of the box.

## Repository Root Resolution

meridian finds the repo root in this order:

1. `MERIDIAN_REPO_ROOT` environment variable (if set)
2. Walk up from `cwd` looking for `.agents/skills/` directory
3. Fall back to `cwd`

## Directory Layout

```
<repo-root>/
├── .agents/
│   ├── agents/              # Agent profiles
│   │   ├── coder.md
│   │   ├── researcher.md
│   │   └── reviewer.md
│   └── skills/              # Skill library
│       ├── run-agent/
│       │   ├── SKILL.md
│       │   └── references/
│       │       ├── default-model-guidance.md
│       │       └── model-guidance/   # custom overrides
│       ├── orchestrate/SKILL.md
│       ├── reviewing/SKILL.md
│       └── scratchpad/SKILL.md
└── .meridian/
    ├── models.toml          # Custom model overrides (optional)
    ├── index/runs.db        # Skill index (auto-generated)
    ├── runs/                # Run artifacts
    ├── workspaces/          # Workspace state
    └── active-workspaces/   # Lock files
```

## Skills

Skills are markdown files at `.agents/skills/*/SKILL.md` with YAML frontmatter.

### Frontmatter fields

```yaml
---
name: review                     # Identifier (defaults to directory name)
description: Code review skill   # One-line description
tags: [quality, ci]              # Metadata tags
user-invocable: false            # Whether users can invoke directly
allowed-tools: Bash(git *)       # Tool allow-list for security gates
---

Skill body (markdown) follows here...
```

All fields are optional. `name` defaults to the parent directory name if omitted.

### Skill indexing

Skills are indexed in SQLite for fast search:

```bash
meridian skills list              # list all discovered skills
meridian skills search "review"   # full-text search
meridian skills show review       # print full SKILL.md content
meridian skills reindex           # rebuild the index
```

### Base skills

meridian automatically injects base skills depending on the launch mode:

| Mode | Base skills |
|------|-------------|
| `standalone` (single run) | `run-agent`, `agent` |
| `supervisor` (workspace) | `run-agent`, `agent`, `orchestrate` |

Requested skills are appended after base skills, with duplicates removed.

## Agent Profiles

Agent profiles live at `.agents/agents/*.md` with YAML frontmatter.

### Frontmatter fields

```yaml
---
name: coder                          # Identifier (defaults to filename stem)
description: Implementation agent    # One-line description
model: gpt-5.3-codex                # Default model
variant: high                        # Variant name
skills: [scratchpad]                 # Attached skill names
tools: [Read, Glob, Grep, Bash]      # Allowed tools
sandbox: unrestricted                # Sandbox / permission mode
variant-models: [claude-opus-4-6]    # Alternative models for variants
---

Agent system prompt (markdown) follows here...
```

### Using agent profiles

```bash
meridian run create -p "Fix the bug" --agent coder
```

When `--agent` is specified, meridian loads the profile and applies its defaults (model, skills, sandbox) unless overridden by CLI flags.

### Sandbox mapping

The `sandbox` field maps to permission tiers:

| Agent sandbox | Permission tier |
|---------------|----------------|
| `read-only` | `read-only` |
| `workspace-write` | `workspace-write` |
| `danger-full-access` | `full-access` |
| `unrestricted` | `full-access` |

CLI `--permission` overrides the agent profile default.

## Models

### Built-in catalog

Six models ship built-in:

| ID | Alias | Harness | Cost | Role |
|----|-------|---------|------|------|
| `claude-opus-4-6` | `opus` | claude | $$$ | Architecture, subtle correctness |
| `gpt-5.3-codex` | `codex` | codex | $ | Fast implementation, code generation |
| `claude-sonnet-4-6` | `sonnet` | claude | $$ | UI iteration, fast generalist |
| `claude-haiku-4-5` | `haiku` | claude | $ | Commit messages, quick transforms |
| `gpt-5.2-high` | `gpt52h` | codex | $$ | Escalation solver |
| `gemini-3.1-pro` | `gemini` | opencode | $$ | Research, multimodal |

### Custom models

Add or override models in `.meridian/models.toml`:

```toml
[[models]]
model_id = "my-custom-model-v1"
aliases = ["mymodel", "mm"]
role = "Custom role"
strengths = "What it does well"
cost_tier = "$$"
harness = "opencode"
```

Custom entries with the same `model_id` as a built-in completely replace the built-in entry.

### Model resolution

```bash
meridian run create -p "..." -m opus           # alias → claude-opus-4-6
meridian run create -p "..." -m mymodel        # custom alias
meridian run create -p "..." -m claude-opus-4-6  # exact ID
```

Resolution order: exact `model_id` match, then alias lookup. Ambiguous aliases produce an error.

```bash
meridian models list                           # show all models
meridian models show opus                      # show model details
```

## Model Guidance

Model guidance files tell the orchestrator which models to pick for different task types.

### File locations

```
.agents/skills/run-agent/references/
├── default-model-guidance.md         # built-in guidance
└── model-guidance/                   # custom overrides (optional)
    ├── 10-implementation.md
    └── 20-review.md
```

### Loading precedence

1. If `model-guidance/*.md` files exist → use only those (sorted by filename)
2. Otherwise → use `default-model-guidance.md`

Custom files completely replace the default. Use numeric prefixes (`10-`, `20-`) to control ordering. `README.md` files in the directory are ignored.

## Environment Variables

### Core

| Variable | Default | Purpose |
|----------|---------|---------|
| `MERIDIAN_REPO_ROOT` | (auto-detect) | Explicit repository root |
| `MERIDIAN_DEPTH` | `0` | Current agent nesting depth |
| `MERIDIAN_MAX_DEPTH` | `3` | Maximum nesting depth |
| `MERIDIAN_WORKSPACE_ID` | (unset) | Auto-scope runs to this workspace |
| `MERIDIAN_WORKSPACE_PROMPT` | (unset) | Full supervisor prompt |
| `MERIDIAN_SUPERVISOR_COMMAND` | (unset) | Override supervisor binary |

### Secrets

| Variable | Purpose |
|----------|---------|
| `MERIDIAN_SECRET_<KEY>` | Injected via `--secret KEY=VALUE`; redacted from all output |
| `ANTHROPIC_API_KEY` | Required for `--mode direct` (DirectAdapter) |

### Guardrails

| Variable | Set by | Purpose |
|----------|--------|---------|
| `MERIDIAN_GUARDRAIL_RUN_ID` | guardrail runner | Current run ID |
| `MERIDIAN_GUARDRAIL_OUTPUT_LOG` | guardrail runner | Path to `output.jsonl` |
| `MERIDIAN_GUARDRAIL_REPORT_PATH` | guardrail runner | Path to `report.md` |

Guardrail scripts do **not** receive `MERIDIAN_SECRET_*` variables (stripped for security).

### Claude-specific

| Variable | Purpose |
|----------|---------|
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | Set via `--autocompact` flag for conversation compaction threshold |
