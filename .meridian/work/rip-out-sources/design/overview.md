# Remove `meridian sources` + Auto-Install Bootstrap

## Goal

Remove meridian's built-in agent package management (`meridian sources` CLI + `lib/install/` engine + auto-install bootstrap) and rely on the `.agents/` directory being populated externally — by `mars`, git submodules, symlinks, or manual copy.

Meridian becomes purely a coordination layer. It reads `.agents/` but never writes to it.

## Design Principles

1. **Meridian is mars-unaware at runtime.** No mars imports, no mars-on-PATH checks, no `mars sync` suggestions in error messages. Meridian reads `.agents/agents/*.md` and `.agents/skills/*/SKILL.md` — it doesn't care how they got there.

2. **Mars and symlinks are recommended in docs.** README shows `mars` as the easy path for managing `.agents/`, with symlinks as an alternative for local dev. But these are documentation recommendations, not runtime dependencies.

3. **No auto-install.** If `meridian spawn -a coder` can't find the agent, it errors with "Agent 'coder' not found in .agents/agents/". No silent git clones.

4. **Clean break.** No migration path from `agents.toml`/`agents.lock`. Users who upgrade delete the old files. Mars has its own config (`mars.toml`/`mars.lock`).

## What Gets Removed

### CLI Layer
- `src/meridian/cli/install_cmd.py` — entire 600-line file. The `meridian sources` command group: `install`, `uninstall`, `update`, `list`, `status`.
- `src/meridian/cli/main.py` — `sources_app` variable and registration block.

### Install Engine (entire module)
- `src/meridian/lib/install/` — 11 files:
  - `bootstrap.py` — auto-install of meridian-base from GitHub
  - `config.py` — `agents.toml` / `agents.local.toml` reading/writing
  - `conflicts.py` — merge conflict detection
  - `deps.py` — skill dependency resolution
  - `discovery.py` — agent/skill discovery from source trees
  - `engine.py` — reconcile/install/remove orchestration
  - `hash.py` — content hashing for change detection
  - `lock.py` — `agents.lock` reading/writing
  - `provenance.py` — source ownership lookups
  - `types.py` — shared types
  - `adapters.py` — git/path source adapters

### Auto-Install Bootstrap (in launch path)
- `src/meridian/lib/launch/resolve.py` — `ensure_bootstrap_ready()` function + bootstrap imports. Called on every spawn to silently install missing agents.
- `src/meridian/lib/launch/plan.py` — `ensure_bootstrap_ready()` call + provenance import. Called on primary agent launch.
- `src/meridian/lib/ops/spawn/prepare.py` — `ensure_bootstrap_ready()` call + provenance import. Called on spawn preparation.

### State Paths
- `src/meridian/lib/state/paths.py` — remove `agents_manifest_path`, `agents_local_manifest_path`, `agents_lock_path`, `agents_cache_dir` fields from `StatePaths`. Remove `agents.toml`/`agents.lock` from gitignore template.
- `src/meridian/lib/ops/config.py` — remove `agents_cache_dir` from bootstrap directory creation.

### Config Files (no longer managed)
- `.meridian/agents.toml` — dead, replaced by `.agents/mars.toml`
- `.meridian/agents.local.toml` — dead
- `.meridian/agents.lock` — dead, replaced by `.agents/mars.lock`
- `.meridian/cache/agents/` — dead, mars has its own cache (`~/.mars/cache/`)

## What Gets Updated

### Launch Path (resolve.py, plan.py, prepare.py)
Remove the `ensure_bootstrap_ready()` call chain. The launch path becomes:
1. Load agent profile from `.agents/agents/{name}.md`
2. If not found → error (no auto-install fallback)
3. Load skills, resolve model, build harness command

The `provenance` lookups (which source installed this agent/skill) also go away — they read `agents.lock` which no longer exists.

### README.md
New install section:

```
## Install

### 1. Install meridian
uv tool install meridian-channel

### 2. Set up your agents (recommended: mars)
# Install mars — the agent package manager
cargo install mars-agents   # or: npm i -g mars-agents

# Initialize and sync
cd your-project
mars init
mars add @haowjy/meridian-base
mars sync

# Optional: link .agents/ into .claude/ for Claude Code
mars link .claude

### Alternative: manual setup
# Copy or symlink agents directly into .agents/
git clone https://github.com/haowjy/meridian-base /tmp/meridian-base
cp -r /tmp/meridian-base/agents/ .agents/agents/
cp -r /tmp/meridian-base/skills/ .agents/skills/
```

### .meridian/.gitignore
Remove `!agents.toml` and `!agents.lock` entries since meridian no longer manages these files.

## Schema Cleanup (reviewer finding)

Remove dead provenance/bootstrap fields from all runtime models. These fields were populated by the install engine; with it gone, they're always empty. Per CLAUDE.md: "No backwards compatibility needed."

Fields to remove everywhere they appear:
- `agent_source: str | None` — which source installed this agent
- `skill_sources: dict[str, str]` — which source installed each skill
- `bootstrap_required_items: tuple[str, ...]` — what the bootstrap wanted to install
- `bootstrap_missing_items: tuple[str, ...]` — what was missing pre-install

These appear in: `launch/types.py`, `launch/resolve.py`, `launch/plan.py`, `launch/session_scope.py`, `launch/process.py`, `launch/runner.py`, `ops/spawn/models.py`, `ops/spawn/plan.py`, `ops/spawn/api.py`, `ops/spawn/execute.py`, `state/session_store.py`, `state/spawn_store.py`.

## Error UX (reviewer finding)

After removing auto-install, missing agents produce confusing errors about builtin defaults (`__meridian-subagent`). Improve:
- Missing agent error: show expected path + point to README
- Doctor: warn when default agent profile doesn't exist on disk (even if it's the builtin default name)

## What Does NOT Change

- Agent profile loading (`lib/catalog/agent.py`) — except better error message
- Skill registry and loading (`lib/catalog/skill.py`)
- All spawn/session/report/work machinery
- Config management (`config.toml`, `models.toml`)
