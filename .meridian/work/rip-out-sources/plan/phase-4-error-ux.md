# Phase 4: Improve Error UX for Missing Agents/Skills

Can run in parallel with Phase 3 (zero file overlap; Phase 4 does not edit `AGENTS.md`).

## Scope
After removing auto-install, users who haven't set up `.agents/` will hit errors. Make those errors helpful. Since mars is now a required bundled dependency, error messages should reference `meridian mars sync`.

Also add a thin `meridian mars` passthrough command in the Meridian CLI so mars flows stay discoverable from the Meridian entry point.

## Changes

### Better missing-agent error message

#### `src/meridian/lib/catalog/agent.py`
- When agent profile is not found (the `FileNotFoundError` path around line 223), improve the error message:

```
Agent 'coder' not found.

Expected: .agents/agents/coder.md

Run `meridian mars sync` to populate your agents directory, or see README.md for manual setup.
```

### Louder missing-skills warning

#### `src/meridian/lib/launch/plan.py` (~line 211) and `src/meridian/lib/ops/spawn/prepare.py` (~line 325)
- Keep as WARNING (not fatal) — degraded is better than blocked
- Improve the warning message to include expected paths:

```
Warning: Skipped unavailable skills: context-handoffs, review
Expected: .agents/skills/context-handoffs/SKILL.md
         .agents/skills/review/SKILL.md
Run `meridian mars sync` to install missing skills.
```

### Doctor default-agent warning

#### `src/meridian/lib/launch/default_agent_policy.py`
- Around line 19: `configured_default_agent_warning()` skips validation when agent equals builtin default. After bootstrap removal, the builtin defaults (`__meridian-orchestrator`, `__meridian-subagent`) may not exist on disk.
- Add a check: if the default agent profile file doesn't exist on disk, warn regardless of whether it's the builtin default name.
- Suggest `meridian mars sync` in the warning.

#### `src/meridian/lib/ops/diag.py`
- Around line 96: ensure `configured_default_agent_warning()` usage properly warns when default agents are missing.

### Doctor warning for legacy install artifacts

#### `src/meridian/lib/ops/diag.py`
- Add a doctor check for legacy install files left behind from pre-mars versions:
  - `.meridian/agents.toml`
  - `.meridian/agents.lock`
  - `.meridian/cache/agents/`
- Emit warning text that these are legacy meridian install artifacts and are safe to delete.

### `meridian mars` passthrough command

#### `src/meridian/cli/main.py`
- Add a new `mars` subcommand that forwards all args directly to the `mars` binary:
  - Thin shell-out only (roughly ~20 lines)
  - Implementation shape: `subprocess.run(["mars"] + args, check=False)` and exit with the child status code
- Keep command behavior intentionally minimal: no local parsing/translation of mars flags.
- Update CLI help text to include `mars`.

### pyproject.toml dependency

#### `pyproject.toml`
- Add `mars-agents` as a dependency (with version constraint). This is what makes the `mars` binary available when users install meridian via `uv tool install meridian-channel`.

```toml
dependencies = [
    "mars-agents>=0.1.0",
    # ... existing deps
]
```

## Verification
- `uv run ruff check .`
- `uv run pyright`
- `uv run meridian doctor` in a repo with no `.agents/` — should warn about missing default agent
- `uv run meridian spawn -a nonexistent --dry-run -p "test"` — should show helpful error with mars suggestion
- `uv run meridian spawn -a coder --dry-run -p "test"` with agent but missing skills — should show warning with paths
- `uv run meridian mars --help` — passthrough executes mars from meridian CLI entry point
