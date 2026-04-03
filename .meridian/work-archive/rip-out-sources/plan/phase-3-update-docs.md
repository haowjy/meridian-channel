# Phase 3: Update ALL Documentation

## Scope
Update all user-facing and developer docs to reflect that meridian no longer manages `.agents/`. Mars is now a bundled PyPI dependency — `uv tool install meridian-channel` installs both. Remove all references to `meridian sources`, `agents.toml`, `agents.lock`, and auto-install bootstrap.

## Files

### `README.md`
- Update install section: `uv tool install meridian-channel` now installs both meridian + mars
- Show project setup flow: `meridian mars init` → `meridian mars add` → `meridian mars sync`
- Add alternative manual setup path (symlinks, git clone) for users who don't want mars
- Remove any `meridian sources` references
- Keep `meridian doctor` and `meridian --version` verification steps

### `AGENTS.md` (source of truth; `CLAUDE.md` is symlink to it)
- Remove references to `meridian sources update`, `meridian sources install`
- Update "Editing Agents & Skills" section with canonical workflow:
  - Edit in source repos/submodules
  - Run `meridian mars sync` to regenerate `.agents/`
  - Do not present direct `.agents/` edits as the default workflow (they are overwritten on next sync)
- Add explicit guardrail note: direct `.agents/` edits are for one-off local testing only and are expected to be overwritten by `meridian mars sync`.
- Add note that `meridian-base/` and `meridian-dev-workflow/` submodules are source repos for package development/publishing, not runtime load paths consumed directly by meridian.
- Remove `agents.toml`/`agents.lock` references
- Add "Upgrading" note: safe to delete `.meridian/agents.toml`, `.meridian/agents.local.toml`, `.meridian/agents.lock`, `.meridian/cache/agents/`

### `INSTALL.md`
- Lines 60+: "Install Agent & Skill Sources" section is entirely `meridian sources ...` commands — rewrite to use mars
- Lines 73+: `meridian sources install @haowjy/meridian-base` → `meridian mars add ...` + `meridian mars sync`
- Lines 123+: `meridian sources list` → remove or replace

### `docs/configuration.md`
- Lines 29-31: repo layout still lists `.meridian/agents.toml`, `.meridian/agents.local.toml`, `.meridian/agents.lock` — remove these entries

### `meridian-base/README.md`
- Update language that still claims meridian auto-bootstraps missing agents.
- Replace setup commands with `meridian mars ...` flow (`meridian mars init`, `meridian mars add`, `meridian mars sync`).

### Smoke tests — remove `sources` references

#### `tests/smoke/quick-sanity.md`
- Line 35: `grep -q 'sources'` in help text check — remove `sources` from expected commands
- Lines 77-83: QS-5 "Sources list [CRITICAL]" — delete this entire test case

#### `tests/smoke/agent-mode.md`
- Line 24: remove `"sources"` from visible commands tuple
- Line 38: remove `"sources"` from visible commands tuple

#### `tests/smoke/install/install-cycle.md`
- Already deleted in Phase 1

#### Smoke tests that use `meridian sources install` as setup

The following smoke tests create scratch repos and install agents via `meridian sources install`. Replace with **direct file writes** to populate `.agents/` — this keeps tests hermetic and CI-friendly without depending on mars or any external tool.

Use the pattern from `tests/smoke/spawn/context-from.md` (line 16) which already writes agent profiles directly via `mkdir -p` + `cat >`. Alternatively, use helpers from `tests/helpers/fixtures.py` (lines 12, 29).

Concrete replacement pattern:
```bash
# Before (old):
uv run meridian sources install "$SMOKE_SOURCE" --name smoke >/dev/null 2>&1

# After (new):
mkdir -p .agents/agents .agents/skills
cat > .agents/agents/__meridian-subagent.md << 'AGENT'
---
model: sonnet
---
You are a test agent.
AGENT
```

Files to update:
- `tests/smoke/output-formats.md` (line 22)
- `tests/smoke/spawn/dry-run.md` (line 23)
- `tests/smoke/spawn/skill-injection.md` (line 35)
- `tests/smoke/fork.md` (line 27)
- `tests/smoke/spawn/error-paths.md` (line 22)
- `tests/smoke/spawn/lifecycle.md` (line 22)
- `tests/smoke/adversarial.md` (line 22 + delete lines 108-120 sources loop stress test)

## Verification
- Read through all modified docs for consistency
- No broken references to removed commands
- `grep -r "sources" README.md INSTALL.md AGENTS.md docs/ tests/smoke/ meridian-base/README.md` — only contextual uses remain (not `meridian sources`)
