# Design: `meridian-agents` Repo + On-Demand Install + Remove Bundled Resources

## Summary

Move all meridian skills and agent profiles out of the Python package into an external `meridian-agents` git repo. Commands that require core meridian agents should auto-install or update them into repo-local `.agents/` when missing. Remove `importlib.resources` bundling, remove the materialization pipeline, and stop treating harness-specific directories as install targets. `--append-system-prompt` is the sole skill delivery mechanism.

Core skills/agents are prefixed with `__` to signal system-level (e.g., `__meridian-orchestrator`). That prefix is a naming convention; authoritative install behavior still comes from exported-source metadata such as `managed = true` and `system = true`.

Implementation should simplify the existing codebase rather than preserve it. Delete obsolete code paths, split mixed-responsibility interfaces, and rename surviving types/functions aggressively when the old names encode the wrong model.

This document is authoritative for the core content shape of the external `meridian-agents` source: what the bootstrap set is, what the shipped repo layout looks like, and how managed core profiles/skills should be presented to users. Install/discovery/bootstrap semantics are owned by [meridian-sync.md](/home/jimyao/gitrepos/meridian-channel/.meridian/work/meridian-agents/meridian-sync.md).

## 1. `meridian-agents` Repo Structure

```
meridian-agents/
  agents/
    __meridian-orchestrator.md
    __meridian-subagent.md
  skills/
    __meridian-orchestrate/
      SKILL.md
    __meridian-spawn-agent/
      SKILL.md
      resources/
        advanced-commands.md
        configuration.md
        creating-agents.md
        debugging.md
  README.md
  LICENSE
```

### Core (prefixed with `__`)
These are required for meridian to function:
- `__meridian-orchestrator` — minimal orchestrator profile
- `__meridian-subagent` — default subagent profile
- `__meridian-orchestrate` — orchestration skill (for the orchestrator)
- `__meridian-spawn-agent` — spawn coordination skill (for the orchestrator + subagents)

### Optional (no prefix, added later)
Curated extras users can opt into:
- `reviewer` agent, `reviewing` skill
- `documenter` agent, `documenting` skill
- `smoke-tester` agent
- `scratchpad` skill
- `mermaid` skill
- etc.

Users can install everything or filter: `meridian install meridian-agents --skills reviewing,mermaid`

## 2. Install/Bootstrap Constraints

The install layer needs a small amount of source-specific knowledge so the core content in this repo can be bootstrapped. The full installer behavior, manifest schema, lock semantics, and source-adapter design are specified in [meridian-sync.md](/home/jimyao/gitrepos/meridian-channel/.meridian/work/meridian-agents/meridian-sync.md). This section only records the assumptions this content design places on that install layer.

### Well-known source shorthand

```python
# In install bootstrap or config helper
WELL_KNOWN_SOURCES = {
    "meridian-agents": AgentSourceConfig(
        name="meridian-agents",
        kind="git",
        url="https://github.com/haowjy/meridian-agents.git",
    ),
}
```

`meridian install meridian-agents` resolves via this table before treating it as an explicit source declaration.

### Auto-install on demand

Before running commands that require the configured default primary agent or default subagent, ensure those agent profiles and their required skills are in place:

1. Resolve the configured default primary agent and default subagent
2. Plan the required runtime asset set and dependency closure
3. If those required assets are missing, follow installed ownership/provenance when present; otherwise ask the install reconciler to ensure Meridian-owned defaults from the configured bootstrap source (default: `meridian-agents`)
4. If install/update fails, fail that command with a clear remediation message

If bootstrap fallback is used for a source that is not yet declared, runtime ensure should add that source to `.meridian/agents.toml` and write the resulting install state to `.meridian/agents.lock` just like an explicit `meridian install` would. This is a normal repo-local install mutation, not a hidden ephemeral fallback.

```python
# In launch/spawn paths that require core agent assets
def plan_required_runtime_assets(repo_root: Path) -> RuntimeAssetPlan:
    """Compute the runtime assets needed by the configured default agents."""
    runtime = load_config(repo_root)
    return RuntimeAssetPlanner(repo_root, runtime).plan()


def ensure_runtime_assets(repo_root: Path, plan: RuntimeAssetPlan) -> None:
    """Ensure the planned runtime assets exist in repo-local `.agents/`."""
    bootstrap_source = resolve_bootstrap_source(repo_root, plan)
    InstallReconciler(repo_root).ensure_assets(plan, bootstrap_source)
```

### Install target

- `.agents/skills/`
- `.agents/agents/`

Harness-specific compatibility paths are not part of install state. If a harness such as Claude needs manual symlinks into `.claude/`, Meridian should warn and tell the user what to do instead of mutating those paths automatically.

### Exported source manifest

Each installable source tree should ship an exported-source manifest, for example `meridian-source.toml`, alongside the `agents/` and `skills/` directories. That manifest should describe:

- exported items as generic records with `kind`, `name`, and destination metadata
- dependency edges (for example, agent -> required skills)
- workflow or bundle dependencies when one exported item expects other exported items to be installed too
- managed/system markers
- optional metadata for future catalog UX

The installer should rely on this manifest for dependency closure and ownership tracking instead of re-deriving everything from profile parsing at runtime. The exact dependency semantics, lock behavior, and pruning rules are defined in [meridian-sync.md](/home/jimyao/gitrepos/meridian-channel/.meridian/work/meridian-agents/meridian-sync.md); this document only requires that the shipped content exposes the metadata needed for those mechanisms.

## 3. Agent Profile Changes

### Rename with `__` prefix

Agent profiles move from hardcoded built-ins to synced files:

**Before** (Python code):
```python
def _builtin_profiles() -> dict[str, AgentProfile]:
    return {"meridian-agent": AgentProfile(...), "meridian-primary": AgentProfile(...)}
```

**After** (synced `.md` files in `.agents/agents/`):
- `.agents/agents/__meridian-orchestrator.md`
- `.agents/agents/__meridian-subagent.md`

The long-term goal is to delete `_builtin_profiles()` as a source of live profile definitions. At most, code may keep a minimal bootstrap recipe and legacy alias migration table while install/bootstrap is being wired.

```python
LEGACY_AGENT_ALIASES = {
    "meridian-agent": "__meridian-subagent",
    "meridian-subagent": "__meridian-subagent",
    "meridian-primary": "__meridian-orchestrator",
}
```

In `settings.py`:
```python
default_primary_agent: str = "__meridian-orchestrator"
default_agent: str = "__meridian-subagent"  # was "meridian-agent"
```

User-facing config keys should be `defaults.primary_agent` for the default orchestrator and `defaults.agent` for the default subagent.

### Missing core assets

If the configured default primary agent, default subagent, or their referenced skills are missing from `.agents/`, commands that require them should first follow installed ownership/provenance when available, then fall back to the configured bootstrap source (default: `meridian-agents`) for missing Meridian-owned defaults. If that fails, those commands should fail with a clear remediation message instead of silently running in a degraded fallback mode.

### `__` prefix convention — don't edit system items

The `__` prefix signals "managed/system item" to humans, but the authoritative install semantics come from source metadata. In practice, `__` items should also be marked `managed/system` in the export manifest and will be overwritten when their source is reinstalled, updated, or upgraded. This is communicated via YAML frontmatter in the files themselves — not CLI warnings. The LLM doesn't read frontmatter, so this is purely for humans who open the file:

```yaml
---
name: __meridian-orchestrate
managed: true
warning: >
  This file is managed by meridian install/update/upgrade. Local edits will be overwritten
  when this source is refreshed.
  To customize, copy this skill and update a copied orchestrator profile to use it:
    cp -r .agents/skills/__meridian-orchestrate .agents/skills/my-orchestrate
    cp .agents/agents/__meridian-orchestrator.md .agents/agents/my-orchestrator.md
    # edit my-orchestrator.md so its skills list includes my-orchestrate
    meridian config set defaults.primary_agent my-orchestrator
---
```

Agent profiles get the same treatment:

```yaml
---
name: __meridian-orchestrator
managed: true
warning: >
  This file is managed by meridian install/update/upgrade. Local edits will be overwritten
  when this source is refreshed.
  To customize, copy this agent and set it as default:
    cp .agents/agents/__meridian-orchestrator.md .agents/agents/my-orchestrator.md
    meridian config set defaults.primary_agent my-orchestrator
---
```

This keeps the guidance exactly where users encounter it — in the file itself. No CLI warnings, no README to find. The `meridian config set` commands need to exist (or similar — could be `meridian config` edits to `.meridian/config.toml`).

### Remove materialization gitignore auto-add

`_ensure_materialized_gitignore()` in `materialize.py` auto-appended `__meridian--*` patterns to the repo's `.gitignore`. This dies with materialization deletion — no separate cleanup needed.

The `.meridian/.gitignore` in `paths.py` (protecting internal state files) is unrelated and stays.

## 4. Removing Bundled Resources

### Delete
- `src/meridian/resources/.agents/` (entire directory — agents/ and skills/)

### Keep
- `src/meridian/resources/default-aliases.toml` (model aliases stay bundled)
- `src/meridian/resources/__init__.py`

### Remove `bundled_agents_root()`
- Delete function from `src/meridian/lib/config/settings.py`
- Remove import + bundled fallback from `SkillRegistry.__init__()` in `skill.py`
- Remove import + bundled fallback from `load_agent_profile()` in `agent.py`

Normal resolution becomes repo-local `.agents/` only. Commands that require the configured default primary agent or default subagent should auto-install from installed provenance or the configured bootstrap source when those required assets are missing instead of relying on bundled resources.

## 5. Removing Materialization

### 5a. Primary launch (`command.py`)
- Remove import of `materialize_for_harness`
- Remove the `materialize_for_harness()` call
- Agent name becomes bare profile name:
  ```python
  agent=profile.name if profile is not None else None,
  ```

### 5b. Spawn execution (`execute.py`)
- Remove imports of `cleanup_materialized, materialize_for_harness`
- Remove `_materialize_session_agent_name()` function
- Remove `_cleanup_session_materialized()` function
- Simplify `_session_execution_context()` — agent name passes through directly

### 5c. Primary launch process (`process.py`)
- Remove import of `cleanup_materialized`
- Remove `_cleanup_launch_materialized()` function
- Remove `_sweep_orphaned_materializations()` function

### 5d. CLI startup (`main.py`)
- Remove materialization cleanup from startup block

### 5e. Diagnostics (`diag.py`)
- Remove `cleanup_materialized` call in `_repair_stale_session_locks()`
- Replace with legacy cleanup (see §8)

### 5f. Delete materialize module
- Delete `src/meridian/lib/harness/materialize.py`
- Delete `tests/harness/test_materialize.py`

### 5g. No harness-specific filesystem mirroring
The install/sync layer should not create `.claude/` compatibility links or any other harness-specific mirrors.

## 6. Skill Injection — No Changes Needed

`--append-system-prompt` already works for all paths:

| Harness | Primary | Spawn |
|---------|---------|-------|
| Claude | `--append-system-prompt` | `--append-system-prompt` |
| Codex | inline in prompt | inline in prompt |
| OpenCode | inline in prompt | inline in prompt |

Session resume: `filter_launch_content()` re-injects skills on resume. Skills stay fresh per design.

## 7. Migration Path

### Legacy `__meridian--` files
Add cleanup to `meridian doctor` that removes stale materialized files:

```python
def _cleanup_legacy_materializations(repo_root: Path) -> int:
    removed = 0
    for dir_name in (".claude/agents", ".claude/skills"):
        target = repo_root / dir_name
        if not target.is_dir():
            continue
        for item in target.glob("__meridian--*"):
            if item.is_file():
                item.unlink()
                removed += 1
            elif item.is_dir():
                shutil.rmtree(item)
                removed += 1
    return removed
```

### Backward compat aliases
- `"meridian-agent"` → `__meridian-subagent`
- `"meridian-subagent"` → `__meridian-subagent`
- `"meridian-primary"` → `__meridian-orchestrator`

Keep aliases in a narrow migration table, not as extra live profile definitions.

### `.gitignore` entries
Old patterns like `.claude/agents/__meridian--*` are harmless (match nothing). No cleanup needed.

## 8. Implementation Sequence

1. **Promote drafts into `meridian-agents`** — copy the drafted skills and agent profiles from `.meridian/work/meridian-agents/drafts/` into the checked-out `meridian-agents` submodule and make that repo the shipped source of truth
2. **Add source adapters + well-known source** — `git`/`path` adapters plus `meridian install meridian-agents` shorthand
3. **Add exported-source manifest support** — dependency closure and ownership should come from source metadata
4. **Add on-demand runtime asset ensure** — runtime asset planner + install reconciler in launch/spawn paths that require the configured default primary/subagent
5. **Delete live built-in profiles** — rename to `__` prefix, replace profile fallbacks with minimal bootstrap/migration data, update `default_agent`
6. **Remove bundled resources** — delete `.agents/`, remove `bundled_agents_root()` and fallbacks
7. **Remove materialization** — delete `materialize.py`, remove all call sites, rename surviving interfaces if old names no longer fit
8. **Add legacy cleanup** — `__meridian--*` removal in doctor
9. **Tests** — `uv run pytest-llm && uv run pyright`

Step 1 is the content publication step that unblocks everything else. Steps 2-4 wire the new install/bootstrap path. Steps 5-6 remove the old bundled fallback. Step 7 is its own cleanup commit. Steps 8-9 are polish.
