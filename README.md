# meridian-channel

[![PyPI](https://img.shields.io/pypi/v/meridian-channel)](https://pypi.org/project/meridian-channel/)
[![Python](https://img.shields.io/pypi/pyversions/meridian-channel)](https://pypi.org/project/meridian-channel/)
[![License](https://img.shields.io/github/license/haowjy/meridian-channel)](LICENSE)
[![CI](https://github.com/haowjy/meridian-channel/actions/workflows/meridian-ci.yml/badge.svg)](https://github.com/haowjy/meridian-channel/actions)

Multi-model agent orchestrator. CLI + MCP server + API tool provider.

`meridian` routes agent runs across Claude, Codex, and OpenCode CLIs with workspace persistence, context pinning, cost tracking, permission tiers, and structured output.

Requires **Python 3.14+**.

## Installation

### As a global CLI tool (recommended)

```bash
uv tool install meridian-channel
pipx install meridian-channel
```

Both `uv tool install` and `pipx install` create an isolated venv and symlink the `meridian` binary to `~/.local/bin/` (like `npx -g` in Node).

### With pip

```bash
pip install meridian-channel
```

If you want this as a project dependency with `uv`, use:

```bash
uv add meridian-channel
```

### From source

```bash
git clone https://github.com/haowjy/meridian-channel.git
cd meridian-channel
uv sync --extra dev
uv run meridian --help
```

Editable local installs also work for global tool workflows:

```bash
uv tool install -e .
pipx install -e .
meridian --version
```

### Shell completions

```bash
meridian completion install             # auto-detect shell, add to config
meridian completion bash >> ~/.bashrc   # manual bash
meridian completion zsh >> ~/.zshrc     # manual zsh
meridian completion fish > ~/.config/fish/completions/meridian.fish
```

## Quick Start

```bash
# Run a one-shot agent task
meridian run create -p "Refactor the auth module" -m claude-opus-4-6

# Start a persistent workspace (supervisor stays alive)
meridian start --name my-feature

# Inside the workspace, runs are scoped automatically
meridian run create -p "Research the current implementation" -s research
meridian run create -p "Implement the changes" -m gpt-5.3-codex -s scratchpad

# Resume a paused workspace
meridian workspace resume

# Check what happened
meridian list
meridian show r1
```

## Architecture

```
┌──────────────────────────────────────────────┐
│              Operation Registry              │
│         (single source of truth)             │
├──────────┬───────────────┬───────────────────┤
│   CLI    │   MCP Server  │   API Tools       │
│ (cyclopts)│  (FastMCP)   │ (DirectAdapter)   │
└──────────┴───────────────┴───────────────────┘
         │          │              │
         └──────────┴──────────────┘
                    │
         ┌──────────┴──────────┐
         │   Execution Engine  │
         │  (async subprocess) │
         └──────────┬──────────┘
                    │
    ┌───────┬───────┼───────┬────────┐
    │Claude │ Codex │OpenCode│ Direct │
    │  CLI  │  CLI  │  CLI   │  API   │
    └───────┴───────┴────────┴────────┘
```

Every operation is defined once in the registry and auto-exposed to all three surfaces: CLI commands, MCP tools, and Anthropic API tool definitions.

## Core Concepts

### Runs

A run is a single agent task: model + skills + prompt + reference files. Runs are tracked in SQLite with full lifecycle (queued → running → succeeded/failed/cancelled).

```bash
meridian run create -p "Fix the failing test" -m gpt-5.3-codex -s scratchpad
meridian run show r1 --include-report
meridian run continue r1 -p "Also update the docs"
meridian run retry r1
```

### Workspaces

A workspace is a persistent session that scopes runs, pins context files, and maintains a summary across conversation compactions.

```bash
meridian workspace start --name auth-refactor
# ... work happens inside the supervisor ...
meridian workspace resume                    # pick up where you left off
meridian workspace resume --fresh            # new conversation, same context
meridian workspace close w1
```

### Skills

Skills are loaded from `.agents/skills/` and composed into prompts. They're indexed in SQLite for fast search.

```bash
meridian skills list
meridian skills search "review"
meridian skills show review
meridian skills reindex
```

### Three Surfaces

| Surface | Mode | `run create` behavior |
|---------|------|----------------------|
| **CLI** | `meridian run create` | Blocks until completion |
| **MCP** | `meridian serve` | Non-blocking (returns immediately, poll with `run show`) |
| **API** | DirectAdapter | Anthropic Messages API with `code_execution` + `allowed_callers` |

## Documentation

| Document | Contents |
|----------|----------|
| [CLI Reference](docs/cli-reference.md) | Every command, flag, and output mode |
| [MCP Tools](docs/mcp-tools.md) | Tool definitions for agent consumers |
| [Workspaces](docs/workspaces.md) | Lifecycle, context pinning, supervisor launch |
| [Safety](docs/safety.md) | Permissions, budgets, guardrails, secrets |
| [Harness Adapters](docs/harness-adapters.md) | Model routing, adapter capabilities |
| [Configuration](docs/configuration.md) | Skills, models, agents, environment |

## Development

```bash
cd meridian-channel
uv sync --extra dev
uv run pytest                # 91 tests
uv run pyright               # strict mode
uv run ruff check .          # lint
```

## License

MIT
