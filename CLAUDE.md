# Development Guide: meridian-channel

## Philosophy

**Meridian-Channel** is a coordination layer for multi-agent systems—not a file system, execution engine, or data warehouse.

### Core Principles

1. **Harness-Agnostic**: Same `meridian` commands work across Claude, Codex, OpenCode, Cursor, **etc.** (extensible to future harnesses) for both primary agents and subagents, with per-harness adapters
2. **Files as Authority**: Markdown files in `.meridian/<space-id>/` are the source of truth. SQLite is optional derived index only
3. **Explicit Over Implicit**: MERIDIAN_SPACE_ID required; no auto-creation or implicit context
4. **Agent Profiles Own Skills**: Static skill definitions in agent profiles, loaded fresh on agent launch/resume
5. **Minimal Constraints**: Agents organize `.meridian/<space-id>/fs/` however they want; Meridian provides container only

### Architecture

- **Space**: Self-contained agent ecosystem with primary + child agents, shared filesystem
- **Primary Agent**: Entry point (any harness), launched via `meridian space start`
- **Agent Profile**: YAML markdown defining capabilities, tools, model, skills
- **Skill**: Domain knowledge/capability loaded fresh on launch/resume (survives context compaction)

## Development

```bash
# Install from source
uv sync --extra dev

# Run tests
uv run pytest

# Type check
uv run pyright

# Dev server (from repo root)
cd ..
./scripts/dev/setup.sh  # creates tmux session
```

See `../CLAUDE.md` for full repo context (backend/frontend/broader project).

## Current Focus

[Insert current phase and work here]
