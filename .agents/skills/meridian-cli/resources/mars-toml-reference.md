# mars.toml Reference

The manifest at `.agents/mars.toml` declares external sources for agents and skills.

## Source Fields

```toml
[sources.meridian-base]
url = "https://github.com/meridian-flow/meridian-base"
version = "v0.1.0"                    # pin to tag (optional)
agents = ["coder", "reviewer"]        # include filter (optional)
skills = ["planning"]                 # include filter (optional)
exclude = ["agent:experimental"]      # exclude filter (optional)
rename = { "reviewer" = "team-reviewer" }  # rename at install (optional)

[sources.local-dev]
path = "./my-local-agents"            # local path source
```

| Field | Type | Description |
|---|---|---|
| `url` | string | Git URL (HTTPS, SSH, or GitHub shorthand) |
| `path` | string | Local directory path (relative to project root) |
| `version` | string | Pin to a semver tag (git sources only) |
| `agents` | array | Only install these agents |
| `skills` | array | Only install these skills |
| `exclude` | array | Exclude these items (`kind:name` format) |
| `rename` | table | Rename items at install time |
| `depends` | array | Source dependencies (other source names) |

A source must have either `url` or `path`, not both.

## Settings

```toml
[settings]
links = [".claude"]     # directories linked via meridian mars link
```

## Item Filtering

Without filters, every agent and skill discovered in a source is installed.

Filter modes are **mutually exclusive** — a source picks one. Precedence (highest first):

- **`only_skills`** / **`only_agents`**: filter by kind, overrides all other filter fields
- **`agents`** / **`skills`**: Include mode. Only items listed in these fields are installed. Both `agents` and `skills` combine into a single include set.
- **`exclude`**: Exclude mode. Install everything except items listed here. Only takes effect when neither `agents` nor `skills` is set — adding `exclude` alongside `agents`/`skills` is silently ignored.
- No filter fields set: install everything.

## Renames

Avoid collisions or customize names:

```toml
[sources.team-agents]
url = "https://github.com/myorg/agents"
rename = { "reviewer" = "team-reviewer", "planning" = "team-planning" }
```

Renames also rewrite `skills: [...]` references in agent frontmatter so dependencies stay connected.

## Source Layout Convention

Sources should follow this structure:

```
source-root/
  agents/
    agent-name.md          # one markdown file per agent
  skills/
    skill-name/
      SKILL.md             # required entry point
      resources/           # optional supporting files
```

A repo with `SKILL.md` at the root (no `agents/`/`skills/` subdirectories) is treated as a single flat skill — the entire repo is installed as one skill directory.

## Example

```toml
[sources.meridian-base]
url = "https://github.com/meridian-flow/meridian-base"

[sources.meridian-dev-workflow]
path = "./meridian-dev-workflow"

[sources.team-agents]
url = "https://github.com/myorg/team-agents"
version = "v1.2.0"
rename = { "reviewer" = "team-reviewer" }

[settings]
links = [".claude"]
```
