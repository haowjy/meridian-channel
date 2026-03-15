# agents.toml Manifest Reference

The manifest at `.meridian/agents.toml` declares external sources for agents and skills. Each `[[sources]]` block is one source — a git repo or local directory to sync from.

## Source Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier (alphanumeric, hyphens, underscores) |
| `kind` | `"git"` or `"path"` | Yes | Source type |
| `url` | string | git only | Full git URL (https or ssh) |
| `path` | string | path only | Local path (absolute, relative to repo root, or `~`) |
| `ref` | string | Optional | Branch, tag, or commit SHA (git only) |
| `items` | array | Optional | Include filter — only install these items |
| `exclude_items` | array | Optional | Exclude filter — install everything except these |
| `rename` | table | Optional | Rename items at install time |

### Validation

- `kind = "git"` requires `url`, must not have `path`
- `kind = "path"` requires `path`, must not have `url` or `ref`
- Source names must be unique across the manifest

## Item Filtering

By default, every agent and skill discovered in a source is installed. Filters narrow the selection:

- **`items` only**: install only listed items (selective sync)
- **`exclude_items` only**: install everything except listed items
- **Both**: `items` defines the initial set, `exclude_items` removes from it

Use selective sync when a source contains many items but you only need a few — it keeps `.agents/` focused and avoids name collisions.

Item format: `{ kind = "agent"|"skill", name = "..." }`

## Renames

Rename items to avoid collisions or customize names for your project. Keys use canonical `kind:name` format:

```toml
rename = { "agent:reviewer" = "team-reviewer", "skill:design" = "team-design" }
```

Renames apply after filtering — the `name` in `items` uses the source name, not the renamed name.

## Example Manifest

```toml
# Core Meridian agents and skills from the official repo.
# Selective sync — only the items needed for orchestration.
[[sources]]
name = "meridian-agents"
kind = "git"
url = "https://github.com/haowjy/meridian-agents.git"
ref = "main"
items = [
  { kind = "agent", name = "__meridian-orchestrator" },
  { kind = "agent", name = "__meridian-subagent" },
  { kind = "skill", name = "__meridian-orchestrate" },
  { kind = "skill", name = "__meridian-spawn-agent" },
]

# Team-shared agents pinned to a release tag.
[[sources]]
name = "team-agents"
kind = "git"
url = "https://github.com/myorg/team-agents.git"
ref = "v1.2.0"
rename = { "agent:reviewer" = "team-reviewer" }

# Local development drafts — path sources re-read on every update.
[[sources]]
name = "local-dev"
kind = "path"
path = "./my-local-agents"
exclude_items = [{ kind = "agent", name = "experimental" }]
```

## Source Layout Convention

The install engine discovers items by conventional directory structure. Sources should be organized as:

```
source-root/
  agents/
    agent-name.md          # One markdown file per agent profile
  skills/
    skill-name/
      SKILL.md             # Required entry point for each skill
      resources/           # Optional supporting files
        reference.md
```

Discovery scans for `agents/*.md` and `skills/*/SKILL.md` relative to the source root. Files outside this convention are ignored.
