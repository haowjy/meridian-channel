# Phase 4: Improve Error UX for Missing Agents

## Scope
After removing auto-install, users who haven't set up `.agents/` will hit errors. Make those errors helpful without making meridian mars-aware at runtime.

## Changes

### Better missing-agent error message

#### `src/meridian/lib/catalog/agent.py`
- When agent profile is not found (the `FileNotFoundError` path around line 223), improve the error message from the generic "not found" to something like:

```
Agent 'coder' not found.

Expected: .agents/agents/coder.md

Set up your agents directory — see README.md for options.
```

- Keep it mars-unaware. Point to README (which recommends mars), not to mars directly.

### Doctor default-agent warning

#### `src/meridian/lib/launch/default_agent_policy.py`
- Around line 19: `configured_default_agent_warning()` skips validation when agent equals builtin default. After bootstrap removal, the builtin defaults (`__meridian-orchestrator`, `__meridian-subagent`) may not exist on disk.
- Add a check: if the default agent profile file doesn't exist on disk, warn about it regardless of whether it's the builtin default.

#### `src/meridian/lib/ops/diag.py`
- Around line 96: `configured_default_agent_warning()` usage — ensure it now properly warns when default agents are missing.

### Git submodule note in docs

#### `README.md` or `AGENTS.md`
- Note that `meridian-base/` and `meridian-dev-workflow/` submodules are source repos for agent packages, not directly consumed by meridian at runtime. They exist for development and publishing.

## Verification
- `uv run ruff check .`
- `uv run pyright`
- `uv run meridian doctor` in a repo with no `.agents/` — should warn about missing default agent
- `uv run meridian spawn -a nonexistent --dry-run -p "test"` — should show helpful error
