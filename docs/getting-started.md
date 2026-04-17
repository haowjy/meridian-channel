# Getting Started

## Prerequisites

Meridian is a coordination layer — it needs at least one harness installed to run agents.

| Harness     | Model prefixes                  | Install                                                              |
| ----------- | ------------------------------- | -------------------------------------------------------------------- |
| Claude Code | `claude-*`, `sonnet*`, `opus*`  | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| Codex CLI   | `gpt-*`, `codex*`, `o3*`, `o4*` | [github.com/openai/codex](https://github.com/openai/codex) |
| OpenCode    | anything else                   | [opencode.ai](https://opencode.ai) |

**Claude Code** is the primary session harness — it supports system prompt injection and interactive use. Codex and OpenCode work well as spawn targets for delegated tasks.

**Platform**: macOS, Linux, WSL.

## Install

```bash
uv tool install meridian-cli
```

If `meridian` is not found after install, run `uv tool update-shell` and restart your shell.

## Initialize a Project

```bash
cd your-repo
meridian init
```

This creates `.meridian/` with default config. Add `.meridian/fs/` and `.meridian/spawns/` to `.gitignore` (or let `meridian init` do it).

## Tool Integration

To expose installed agent packages to a harness tool directory (`.claude/`, `.cursor/`, etc.), use the `--link` flag:

```bash
meridian init --link .claude
```

Or link an existing `.agents/` after the fact:

```bash
meridian mars link .claude
```

This symlinks `.agents/` into the target directory so harnesses discover the agents and skills without duplication.

## Verify Setup

```bash
meridian config show   # confirm resolved config
meridian models list   # confirm available models
meridian doctor        # check harness connectivity
```

## Multi-Repo Workspace (optional)

If you work across multiple repos and want agents to see sibling directories, set up a local workspace file:

```bash
meridian workspace init   # creates workspace.local.toml, adds .git/info/exclude coverage
```

Edit `workspace.local.toml` to declare which repos to include:

```toml
[[context-roots]]
path = "../sibling-repo"
```

Each enabled, existing root is projected to harness launches automatically — `--add-dir` for Claude Code, `OPENCODE_CONFIG_CONTENT` for OpenCode. See [configuration.md](configuration.md#workspace) for full schema and per-harness details.

## Next Steps

- [commands.md](commands.md) — full CLI reference
- [configuration.md](configuration.md) — config keys, model routing, environment variables
