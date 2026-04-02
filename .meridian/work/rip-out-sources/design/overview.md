# Remove `meridian sources` + Auto-Install Bootstrap

## Goal

Remove meridian's built-in agent package management (`meridian sources` CLI + `lib/install/` engine + auto-install bootstrap) and rely on the `.agents/` directory being populated externally — by `mars`, git submodules, symlinks, or manual copy.

Meridian becomes purely a coordination layer. It reads `.agents/` but never writes to it.

## Design Principles

1. **Mars is a required dependency.** Mars-agents publishes platform-specific wheels to PyPI via maturin (`bindings = "bin"`). Meridian-channel declares `mars-agents` as a required dependency. `uv tool install meridian-channel` installs both — `mars` and `meridian` end up in the same `bin/`. One install command gets everything.

2. **Meridian is mars-unaware at runtime for the launch path.** The spawn/launch/session machinery reads `.agents/` — it doesn't import mars, call mars, or check if mars is on PATH. The `.agents/` directory is the contract.

3. **Error messages CAN reference mars.** Since mars is a bundled required dep (not an external tool the user might not have), error messages like "Run `meridian mars sync` to populate .agents/" are helpful, not presumptuous. This is like pip suggesting `pip install X` — it knows pip is available.

4. **No auto-install.** If `meridian spawn -a coder` can't find the agent, it errors clearly. No silent git clones. But the error can suggest `meridian mars sync`.

5. **Clean break.** No migration path from `agents.toml`/`agents.lock`. Users who upgrade delete the old files. Mars has its own config (`mars.toml`/`mars.lock`).

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

### CLI passthrough (`src/meridian/cli/main.py`)
Add `meridian mars ...` as a thin passthrough command that shells out to `mars` with forwarded arguments. This keeps mars workflows discoverable from the Meridian CLI without coupling launch/runtime behavior to mars internals.

### README.md
New install section:

```
## Install

uv tool install meridian-channel   # installs both meridian + mars

## Set up your project

cd your-project
meridian mars init                 # scaffold mars.toml
meridian mars add @haowjy/meridian-base  # add base agents
meridian mars sync                 # populate .agents/

# Optional: link .agents/ into .claude/ for Claude Code
meridian mars link .claude

## Alternative: manual setup (without mars)
# Copy or symlink agents directly into .agents/
git clone https://github.com/haowjy/meridian-base /tmp/meridian-base
cp -r /tmp/meridian-base/agents/ .agents/agents/
cp -r /tmp/meridian-base/skills/ .agents/skills/
```

### pyproject.toml
Add mars-agents as a dependency:
```toml
[project]
dependencies = [
    "mars-agents>=0.1.0",
    # ... existing deps
]
```

Mars-agents publishes platform-specific wheels via maturin. See `.meridian/work/agent-package-management/design/pypi-distribution.md` for the maturin setup pattern (same as ruff/uv).

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

After removing auto-install, missing agents produce confusing errors about builtin defaults (`__meridian-subagent`). Since mars is now a bundled dependency, errors can reference it directly. Improve:
- Missing agent error: show expected path + suggest `meridian mars sync` + point to README
- Missing skills warning: make it louder with expected paths (keep as warning, not fatal — degraded is better than blocked)
- Doctor: warn when default agent profile doesn't exist on disk (even if it's the builtin default name)

## What Does NOT Change

- Agent profile loading (`lib/catalog/agent.py`) — except better error message
- Skill registry and loading (`lib/catalog/skill.py`)
- All spawn/session/report/work machinery
- Config management (`config.toml`, `models.toml`)
