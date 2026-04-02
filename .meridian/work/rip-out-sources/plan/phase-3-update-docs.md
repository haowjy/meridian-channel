# Phase 3: Update ALL Documentation

## Scope
Update all user-facing and developer docs to reflect that meridian no longer manages `.agents/`. Recommend mars + symlinks. Remove all references to `meridian sources`, `agents.toml`, `agents.lock`, and auto-install bootstrap.

## Files

### `README.md`
- Update install section to show mars as recommended setup
- Add alternative manual setup path (symlinks, git clone)
- Remove any `meridian sources` references
- Keep `meridian doctor` and `meridian --version` verification steps

### `AGENTS.md` (source of truth; `CLAUDE.md` is symlink to it)
- Remove references to `meridian sources update`, `meridian sources install`
- Update "Editing Agents & Skills" section: remove the submodule workflow that runs `meridian sources update --force`. Replace with guidance on editing via mars source repos or direct `.agents/` edits.
- Remove `agents.toml`/`agents.lock` references
- Add "Upgrading" note: safe to delete `.meridian/agents.toml`, `.meridian/agents.local.toml`, `.meridian/agents.lock`, `.meridian/cache/agents/`

### `INSTALL.md`
- Lines 60+: "Install Agent & Skill Sources" section is entirely `meridian sources ...` commands — rewrite to use mars
- Lines 73+: `meridian sources install @haowjy/meridian-base` → `mars add ...` + `mars sync`
- Lines 123+: `meridian sources list` → remove or replace

### `docs/configuration.md`
- Lines 29-31: repo layout still lists `.meridian/agents.toml`, `.meridian/agents.local.toml`, `.meridian/agents.lock` — remove these entries

### Smoke tests — remove `sources` references

#### `tests/smoke/quick-sanity.md`
- Line 35: `grep -q 'sources'` in help text check — remove `sources` from expected commands
- Lines 77-83: QS-5 "Sources list [CRITICAL]" — delete this entire test case

#### `tests/smoke/agent-mode.md`
- Line 24: remove `"sources"` from visible commands tuple
- Line 38: remove `"sources"` from visible commands tuple

#### `tests/smoke/install/install-cycle.md`
- Already deleted in Phase 1

#### `tests/smoke/output-formats.md`
- Line 22: `meridian sources install` setup line — rewrite to assume `.agents/` is pre-populated

#### `tests/smoke/spawn/dry-run.md`
- Line 23: `meridian sources install` setup — rewrite

#### `tests/smoke/spawn/skill-injection.md`
- Line 35: `meridian sources install` setup — rewrite

#### `tests/smoke/fork.md`
- Line 27: `meridian sources install` setup — rewrite

#### `tests/smoke/spawn/error-paths.md`
- Line 22: `meridian sources install` setup — rewrite

#### `tests/smoke/spawn/lifecycle.md`
- Line 22: `meridian sources install` setup — rewrite

#### `tests/smoke/adversarial.md`
- Line 22: `meridian sources install` setup — rewrite
- Lines 108-120: `sources install`/`uninstall` loop stress test — delete

## Verification
- Read through all modified docs for consistency
- No broken references to removed commands
- `grep -r "sources" README.md INSTALL.md AGENTS.md docs/ tests/smoke/` — only contextual uses remain (not `meridian sources`)
