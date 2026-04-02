# Phase 4: Improve Error UX for Missing Agents/Skills

Can run in parallel with Phase 3 (zero file overlap).

## Scope
After removing auto-install, users who haven't set up `.agents/` will hit errors. Make those errors helpful. Since mars is now a bundled PyPI dependency, error messages CAN reference `mars sync` — it's like pip suggesting `pip install X`.

## Changes

### Better missing-agent error message

#### `src/meridian/lib/catalog/agent.py`
- When agent profile is not found (the `FileNotFoundError` path around line 223), improve the error message:

```
Agent 'coder' not found.

Expected: .agents/agents/coder.md

Run `mars sync` to populate your agents directory, or see README.md for manual setup.
```

### Louder missing-skills warning

#### `src/meridian/lib/launch/plan.py` (~line 211) and `src/meridian/lib/ops/spawn/prepare.py` (~line 325)
- Keep as WARNING (not fatal) — degraded is better than blocked
- Improve the warning message to include expected paths:

```
Warning: Skipped unavailable skills: context-handoffs, review
Expected: .agents/skills/context-handoffs/SKILL.md
         .agents/skills/review/SKILL.md
Run `mars sync` to install missing skills.
```

### Doctor default-agent warning

#### `src/meridian/lib/launch/default_agent_policy.py`
- Around line 19: `configured_default_agent_warning()` skips validation when agent equals builtin default. After bootstrap removal, the builtin defaults (`__meridian-orchestrator`, `__meridian-subagent`) may not exist on disk.
- Add a check: if the default agent profile file doesn't exist on disk, warn regardless of whether it's the builtin default name.
- Suggest `mars sync` in the warning.

#### `src/meridian/lib/ops/diag.py`
- Around line 96: ensure `configured_default_agent_warning()` usage properly warns when default agents are missing.

### Git submodule note in docs

#### `AGENTS.md`
- Note that `meridian-base/` and `meridian-dev-workflow/` submodules are source repos for agent packages, not directly consumed by meridian at runtime. They exist for development and mars package publishing.

### pyproject.toml dependency

#### `pyproject.toml`
- Add `mars-agents` as a dependency (with version constraint). This is what makes the `mars` binary available when users install meridian via `uv tool install meridian-channel`.

```toml
dependencies = [
    "mars-agents>=0.1.0",
    # ... existing deps
]
```

Note: mars-agents won't be on PyPI yet when we first land this. Use an optional dependency group initially if needed, and promote to required once mars-agents publishes its first release.

## Verification
- `uv run ruff check .`
- `uv run pyright`
- `uv run meridian doctor` in a repo with no `.agents/` — should warn about missing default agent
- `uv run meridian spawn -a nonexistent --dry-run -p "test"` — should show helpful error with mars suggestion
- `uv run meridian spawn -a coder --dry-run -p "test"` with agent but missing skills — should show warning with paths
