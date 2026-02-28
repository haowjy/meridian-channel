# meridian-channel

[![PyPI](https://img.shields.io/pypi/v/meridian-channel)](https://pypi.org/project/meridian-channel/)
[![Python](https://img.shields.io/pypi/pyversions/meridian-channel)](https://pypi.org/project/meridian-channel/)
[![License](https://img.shields.io/github/license/haowjy/meridian-channel)](LICENSE)
[![CI](https://github.com/haowjy/meridian-channel/actions/workflows/meridian-ci.yml/badge.svg)](https://github.com/haowjy/meridian-channel/actions)

Multi-model agent orchestrator with a primary agent (root agent launched in a space). Run tasks across Claude, Codex, and OpenCode from Claude, Codex, or Opencode.

## What it does

`meridian` wraps multiple AI coding CLIs behind a single interface. You pick a model, write a prompt, and it handles routing to the right CLI, tracking runs in SQLite, streaming output, and persisting results.

It exposes the same operations as a CLI, an MCP server (`meridian serve`), and as Anthropic API tool definitions — so both humans and agents can use it.

## Install

Requires **Python 3.12+** and at least one of: [Claude CLI](https://docs.anthropic.com/en/docs/claude-code), [Codex CLI](https://github.com/openai/codex), or [OpenCode](https://opencode.ai).

```bash
# Recommended — isolated install, adds `meridian` to PATH
uv tool install meridian-channel

# Or with pipx
pipx install meridian-channel

# Or plain pip
pip install meridian-channel
```

### From source

```bash
git clone https://github.com/haowjy/meridian-channel.git
cd meridian-channel
uv sync --extra dev
uv run meridian --help
```

### Shell completions

```bash
meridian completion install
```

## Usage

### Run a task

```bash
meridian run create -p "Fix the failing test" -m claude-sonnet-4-6
```

This blocks until the run finishes, streaming output to your terminal.

### Run in the background

```bash
RUN_ID=$(meridian run create --background -p "Refactor auth module" -m gpt-5.3-codex)
meridian run wait $RUN_ID
meridian run show $RUN_ID --include-report
```

### Use skills and reference files

```bash
meridian run create -p "Review this code" -m claude-opus-4-6 -s review -f src/main.py
```

### Continue or retry a run

```bash
# Pick up where the last run left off (forks the conversation)
meridian run continue @latest -p "Also add tests"

# Retry the last failure
meridian run retry @last-failed
```

### Check run history

```bash
meridian run list
meridian run stats
meridian run show @latest --include-report
```

### Spaces

Spaces group related runs under a persistent session with pinned context, and `space start` launches the space's primary agent.

```bash
meridian space start --name auth-refactor  # launches the primary agent for this space
meridian run create -p "Research the current implementation" -s research
meridian run create -p "Implement the changes" -m gpt-5.3-codex
meridian space close w1
```

### Configuration

All state lives in `.meridian/` in your repo root (created automatically on first run). Config is optional — defaults work out of the box.

```bash
meridian config init                        # scaffold .meridian/config.toml
meridian config set defaults.max_retries 5  # change a setting
meridian config show                        # see all resolved values
```

### MCP server

```bash
meridian serve
```

Exposes all operations as MCP tools over stdio.

## Philosophy

Meridian is **not** a file system, project manager, or execution engine. It is a **coordination layer** that:

- **Manages agent ecosystem metadata**: Agent profile definitions, skill definitions, space context
- **Provides shared working filesystem**: `.meridian/<space-id>/fs/` where agents read/write collaborative work
- **Persists collaborative work**: Everything in `fs/` is committed to git (agents decide organization)
- **Indexes ephemeral state**: Run history, sessions, artifacts (computed, not authoritative)
- **Uses markdown/JSON files as source of truth**: No SQLite-as-authority (SQLite is optional indexing)
- **Stays harness-agnostic**: Same `meridian` commands work across Claude, Codex, OpenCode, Cursor, **etc.** (extensible to future harnesses) for both primary agents and subagents, with per-harness adapters

## Core Concepts

**Space**: A self-contained agent ecosystem with shared context
- Primary agent: Entry point (any harness)
- Child agents: Spawned from primary (any harness)
- Filesystem: `.meridian/<space-id>/fs/` (git-committed)
- Metadata: `.meridian/<space-id>/space.md`, agents, skills

**Agent Profile**: Defines what an agent is (markdown + YAML frontmatter)
- Capabilities (tools, model)
- Skills (built-in knowledge/tools)
- System prompt
- Located in `.meridian/<space-id>/agents/` or `.claude/agents/`

**Skill**: Domain knowledge or capability (markdown SKILL.md)
- Located in `.meridian/<space-id>/skills/`
- Loaded by agents on startup
- Agents can read/search space skills

## Development

```bash
uv sync --extra dev
uv run pytest
uv run pyright
uv run ruff check .
```

## License

MIT
