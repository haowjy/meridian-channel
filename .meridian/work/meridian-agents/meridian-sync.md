# Managed Agent Sources (`meridian install`)

**Status:** revised design

## 1. Goal

Replace Meridian's ambient agent/skill discovery model with a repo-local installation model:

- installed agents and skills live in `.agents/`
- Meridian discovers from `.agents/` only
- external content is brought in through `meridian install` / `update` / `upgrade`
- global search paths, harness-specific install mirrors, and temp materialized copies are deleted

This plan is intentionally both additive and subtractive: implement managed installs, then remove the old discovery and reconciliation machinery that becomes unnecessary.

This document is the authoritative plan for install, discovery, lock/manifest state, runtime bootstrap, and deletion of legacy sync/materialization behavior. The companion documents in `.meridian/work/meridian-agents/` describe what content should live in the external source, not how the installer works.

## 1a. Implementation Posture

This redesign should fit into the existing codebase by simplifying it, not by layering a second system on top of the first.

Implementation rules:

- prefer deleting obsolete code paths over preserving compatibility shims
- refactor existing interfaces when they no longer match the new model
- rename aggressively when old names (`sync`, `materialize`, `bundled`, `reconcile`) would preserve the wrong mental model
- do not leave dead fallback logic, unused config paths, or legacy helpers that no longer make architectural sense
- if an existing abstraction now mixes runtime policy and install mechanism, split it instead of stretching it further

### Clean Breaks Are Preferred

This project has no external users and no backward-compatibility requirement. Prefer a clean, internally consistent system over migration machinery.

Specific consequences:

- old `.meridian/config.toml` `[sync.sources]` state is legacy and may be ignored
- old `.meridian/sync.lock` state is legacy and may be ignored
- the new install model starts from `.meridian/agents.toml` and `.meridian/agents.lock`
- first use of the new install model may behave like a fresh reinstall from declared sources
- do not preserve compatibility for old hash formats, key formats, or config schemas unless doing so is simpler than deleting them

## 2. Core Decisions

### `.agents/` is the only authority

Meridian-owned agent and skill content lives only in:

- `.agents/agents/`
- `.agents/skills/`

There is no second Meridian-managed copy under `.claude/`, `.codex/`, `.opencode/`, or home-directory paths.

### No global discovery

Meridian should stop discovering agents and skills from:

- `~/.claude/...`
- `~/.codex/...`
- `~/.opencode/...`
- repo-local `.claude/...`
- repo-local `.codex/...`
- repo-local `.opencode/...`
- bundled package resources

Discovery becomes simple and deterministic: scan the current repo's `.agents/` only.

### No install-time harness mirroring

`meridian install` writes only to `.agents/`.

If a harness needs manual compatibility wiring, Meridian may warn and print instructions, but it should not mutate harness-specific directories automatically. For Claude, that warning can suggest:

```bash
ln -s ../.agents/agents .claude/agents
ln -s ../.agents/skills .claude/skills
```

That remains user-owned setup, not install-layer behavior.

### No temp materialized agent/skill copies

The old "reconcile search paths into temporary harness-facing agents/skills" model should be removed. Runtime should use installed repo-local assets directly. If a harness has special lookup requirements, handle that in the harness adapter/runtime layer without making those paths part of Meridian discovery or install state.

### No bundled steady-state fallback

Bundled `.agents` resources should be removed. Code may keep a minimal bootstrap/install recipe for the built-in `meridian-agents` source, but not live profile or skill definitions. Commands that do not require installed default agents still work normally. Commands that do require them should:

1. check repo-local `.agents/`
2. compute the required runtime asset set for the configured default orchestrator and default subagent
3. ask the install reconciler to ensure those assets exist from installed provenance or the configured bootstrap source
4. fail that command with a clear error if install/update fails

The base CLI still works without installed agents, but orchestration commands that need their configured default agents should not silently fall back to a second source of truth.

If runtime ensure has to fall back to the bootstrap source and that source is not yet declared, it should add that source to `.meridian/agents.toml` and write the resulting install to `.meridian/agents.lock` exactly as a normal install would. Runtime bootstrap is a repo-local install mutation, not an ephemeral hidden fallback.

### Code owns recipes, not live content

Python code should contain only:

- the built-in alias/default for `meridian-agents`
- bootstrap/install machinery
- source adapter registration
- manifest + lock parsing for `.meridian/agents.toml` and `.meridian/agents.lock`

Python code should not contain:

- live default agent profile definitions
- live default skill dependency lists
- a second authoritative copy of core profile metadata

## 3. User Model

### Primary UX

```bash
meridian install meridian-agents
meridian install myorg/team-agents --ref v1.2.0
meridian install ./local/agents --name local

meridian update
meridian update --source meridian-agents

meridian upgrade
meridian upgrade --source meridian-agents

meridian remove meridian-agents
```

`install` is the user-facing entrypoint. Internally, the implementation can still be a sync engine, but "sync" does not need to be the primary CLI noun anymore.

### What `install` does

`meridian install <source>`:

1. resolves the source (`owner/repo`, well-known alias, or local path)
2. writes the source declaration to `.meridian/agents.toml`
3. discovers agents and skills from that source
4. copies them into `.agents/`
5. writes `.meridian/agents.lock`

### What `update` does

`meridian update` reapplies installed sources from the lock file without re-resolving floating refs.

For `path` sources, `update` simply reinstalls from the current local tree.

### What `upgrade` does

`meridian upgrade` re-resolves floating refs such as branches, installs the new content into `.agents/`, and rewrites the lock file.

For `path` sources, `upgrade` is equivalent to `update`.

There is no separate `latest` keyword or version-range syntax such as `>=1.2`. Source refs are plain Git refs: branch, tag, or commit. "Latest" simply means "whatever a floating ref resolves to when `upgrade` runs."

### What `remove` does

`meridian remove <name>` removes the source from the manifest and uninstalls its managed content from `.agents/` when safe.

## 4. Project Files

Keep this state project-local:

```text
.meridian/
├── config.toml         # meridian runtime behavior only
├── agents.toml         # declared external agent/skill sources
├── agents.lock         # resolved commits + installed hashes
└── cache/
    └── agents/
```

### Why split `agents.toml` from `config.toml`?

`config.toml` is runtime/policy config. Source declarations are closer to a dependency manifest. Splitting them avoids turning `.meridian/config.toml` into a grab bag of unrelated concerns.

## 5. Source Manifest

`.meridian/agents.toml`:

```toml
[[sources]]
name = "meridian-agents"
kind = "git"
url = "https://github.com/haowjy/meridian-agents.git"
ref = "main"

[[sources]]
name = "team"
kind = "git"
url = "https://github.com/myorg/team-agents.git"
ref = "v1.2.0"
items = [
  { kind = "skill", name = "reviewing" },
  { kind = "skill", name = "documenting" },
  { kind = "agent", name = "reviewer-solid" },
  { kind = "agent", name = "documenter" },
]
rename = { "agent:reviewer-solid" = "team-reviewer" }

[[sources]]
name = "local"
kind = "path"
path = "./tools/meridian-agents"
```

### Source fields

| Field | Type | Description |
|------|------|-------------|
| `name` | string | Unique source name |
| `kind` | string | Source adapter kind: `git` or `path` |
| `url` | string | Git URL for `git` sources |
| `path` | string | Local path for `path` sources |
| `ref` | string | Branch, tag, or commit for `git` sources |
| `items` | item[] | Optional include list of exported items |
| `exclude_items` | item[] | Optional exclude list of exported items |
| `rename` | map | Destination rename map keyed by `kind:name` |

Where an item selector looks like:

```toml
{ kind = "agent", name = "reviewer-solid" }
```

Version-range semantics are intentionally out of scope. If users want a moving target, they should use a floating branch ref such as `main` and run `meridian upgrade`. If they want stability, they should use an exact tag or commit.

CLI convenience flags such as `--agents` and `--skills` can still exist, but they should compile down to generic item selectors in the manifest and lock.

Canonical item identity throughout the install system should be `agent:name` / `skill:name`. Use that shape consistently for selectors, dependency edges, rename keys, lock ownership records, and any other item-keyed state. Destination paths such as `.agents/agents/<name>.md` remain separate from item identity.

### Source kind adapters

Source resolution should be adapter-based from the beginning:

- `git` -> clone/fetch/archive a git-backed exported source tree
- `path` -> read a local exported source tree directly

Each source adapter should provide a small common interface:

- `resolve(source)` -> resolved identity (`ref`/commit, stat info, etc.)
- `fetch(source, resolved)` -> local source tree path
- `describe(tree)` -> discovered installable items from conventional layout

This keeps GitHub details inside the `git` adapter instead of leaking them into the manifest schema or install reconciler.

### Well-known sources

Add a small alias table so:

```bash
meridian install meridian-agents
```

expands to the canonical repo without the user having to type `haowjy/meridian-agents`.

## 6. Lock File

`.meridian/agents.lock` records:

- source name
- source kind (`git` or `path`)
- source locator (`url` or `path`)
- requested ref
- resolved identity blob owned by the source adapter
- exported item snapshot for that source
- ownership records for each installed item, including source provenance and destination path
- installed tree hash
- last installed timestamp

This remains the mechanism for:

- reproducible `update`
- lock-vs-local modification checks
- safe pruning
- provenance

`agents.lock` is a resolved install snapshot, not a mutex-style runtime lock file. In the long-term naming model, `.lock` should be reserved for developer-facing resolved state, while advisory file-lock artifacts should move to hidden `.flock` sidecars or another internal-only path.

## 7. Install Rules

### Discovery format

Installable source trees use conventional layout only:

```text
agents/<agent-name>.md
skills/<skill-name>/SKILL.md
```

There is no required Meridian-specific source manifest. Any repo or local directory with that layout is installable.

The installer should discover:

- agents from `agents/*.md`
- skills from `skills/*/SKILL.md`

Default behavior is to install every discovered item in the source. Consumer-side selectors in `.meridian/agents.toml` may narrow or exclude discovered items, and `rename` may change their installed destination names.

There is no source-authored dependency closure in the current model. If a profile expects certain skills or companion agents, that is content-level convention, not installer-enforced metadata.

Do not support shared ownership for the same destination item across sources. If two configured sources resolve to the same destination item in `.agents/`, that is a hard error.

### Collision rules

Keep only install-time collisions:

- two configured sources want the same destination name in `.agents/` -> hard error
- unmanaged file already exists at the destination in `.agents/` -> hard error unless `--force`
- managed file was locally modified -> conflict behavior based on lock vs local hash, with `--force` override

Delete discovery-time cross-root conflict logic entirely. There is only one root now.

### Hashing and local edits

Keep the existing tree-hash idea:

- skills hash as directory trees
- agents hash as single files
- local-modification checks and installed hashes use normalized visible content for both agents and skills

Normalize only mechanical formatting such as line endings and a final trailing newline. Do not ignore frontmatter or any other visible file content.

Because this is a clean break, the new hashing rule does not need to preserve compatibility with legacy body-only hashes.

## 8. Runtime Behavior

### Repo-local discovery only

Catalog resolution should become:

- agents: `.agents/agents/*.md`
- skills: `.agents/skills/*/SKILL.md`

No global path merging. No harness path merging. No bundled resource fallback in normal operation.

### Commands that require configured default agents

Commands like orchestrator launch or spawn that require the configured default primary agent or default subagent should call something like:

```python
plan = plan_required_runtime_assets(repo_root)
ensure_runtime_assets(repo_root, plan)
```

Behavior:

1. `plan_required_runtime_assets()` reads runtime config and determines the default primary agent and default subagent
2. it plans the required root agent items that must exist in `.agents/`
3. `ensure_runtime_assets()` checks whether those agent assets exist locally
4. if any are missing, it first follows installed ownership/provenance when present; if a missing Meridian-owned default has never been installed, it falls back to the configured bootstrap source
5. if bootstrap fallback is used for a source not yet declared, it writes that source declaration to `.meridian/agents.toml` and records the realized install in `.meridian/agents.lock`
6. dry-run paths may plan and report missing assets, but they must not mutate install state
7. if ensure still fails on a mutating command, fail that command with a clear remediation message

Commands that do not require those assets should still work without any install step.

The user-facing runtime config should expose these defaults as `defaults.primary_agent` for the default orchestrator and `defaults.agent` for the default subagent.

Install/provenance decisions come from `.meridian/agents.toml`, `.meridian/agents.lock`, and the discovered source layout. Runtime profile files under `.agents/` are the content consumed by the harness at launch time, but they are not the source of truth for managed provenance.

### Claude-specific note

If Claude needs `.claude/agents` and `.claude/skills` for `--agent` lookup, that is a harness/runtime concern, not an install concern. The install flow may warn, but should not write those paths automatically.

### Harness binding seam

Keep a narrow harness-side hook for future runtime quirks, even if most harnesses simply consume `.agents/` directly:

- `prepare_runtime_view()` or `bind_assets()`

This hook belongs in the harness adapter layer. It should not become a second install target or a second discovery root.

### Default bootstrap source

By default, the configured bootstrap source for Meridian-owned defaults is the built-in `meridian-agents` source. Users may override that source or its ref in `.meridian/agents.toml`. Runtime ensure logic should follow installed ownership/provenance first, and use the bootstrap source only for missing Meridian-owned defaults that are not already installed from another source. When bootstrap fallback is used for an undeclared source, Meridian should persist that source in `.meridian/agents.toml` and record the install in `.meridian/agents.lock` so future `update`, `upgrade`, and `remove` operate on normal manifest state.

## 9. Deletion Scope

This redesign should deliberately delete:

- search-path config for local/global agent and skill roots
- catalog reconciliation across multiple roots
- bundled `.agents` resource loading
- temp materialized agents/skills for harnesses
- install/sync code that writes `.claude/`
- conflict logic that exists only because multiple discovery roots are merged

## 10. Implementation Order

### Phase 0: Promote drafts into `meridian-agents`

- Treat [drafts](/home/jimyao/gitrepos/meridian-channel/.meridian/work/meridian-agents/drafts) as the staging area, not the shipping source of truth
- Copy the drafted agent profiles and skills into the checked-out [meridian-agents](/home/jimyao/gitrepos/meridian-channel/meridian-agents) submodule
- Keep the submodule in conventional `agents/` and `skills/` layout
- Make sure the submodule contains the minimum bootstrap set needed by the configured default orchestrator and subagent
- Normalize the draft content so the shipped profiles and skills match the current runtime/bootstrap policy
- After promotion, future edits should land in the submodule first; drafts should either be removed or clearly treated as temporary scratch space

### Phase 1: Introduce managed source manifest + lock

- Add `.meridian/agents.toml` models and I/O
- Treat old sync config/lock state as legacy and start cleanly from `.meridian/agents.toml` + `.meridian/agents.lock`
- Add `kind = "git" | "path"` source adapters
- Add layout-based source discovery for `agents/*.md` and `skills/*/SKILL.md`
- Keep the core source-resolution, hashing, and lock concepts
- Wire `meridian install`, `update`, `upgrade`, `remove`
- Rename implementation types/functions to match the new install/source model where needed

### Phase 2: Make `.agents` the only install target

- Remove `.claude` writes from install/sync code
- Remove `.claude` conflict checks from the install engine
- Update command help/output to describe `.agents` only
- Add manual warning text for Claude users instead of automatic mutation

### Phase 3: Delete ambient discovery

- Remove global/local multi-root search path config
- Make catalog discovery resolve from repo-local `.agents/` only
- Remove duplicate-resolution logic across search roots
- Delete compatibility helpers that only existed to merge or reconcile multiple discovery roots

### Phase 4: Delete materialization and bundled resource fallback

- Remove bundled `.agents` resources from the package
- Remove materialization helpers and tests
- Remove runtime code paths that generate temp agent/skill copies
- Rename surviving interfaces so nothing still sounds like a materialization/reconciliation pipeline

### Phase 5: Auto-ensure configured default agents only where needed

- Add a runtime asset planner in the launch/spawn entrypoints that actually need default runtime agents
- Add an install reconciler entrypoint that can ensure a planned asset set exists
- Resolve the configured default primary agent and default subagent as required root agent items
- Auto-install/update from installed provenance or the configured bootstrap source when those required agents are missing
- Persist bootstrap-source fallback into `.meridian/agents.toml` and `.meridian/agents.lock` using the same ownership/provenance model as explicit installs
- Keep dry-run planning read-only
- Fail those commands clearly if install/update fails
- Leave non-agent-dependent CLI commands alone
- Refactor existing launch/spawn wiring rather than scattering bootstrap checks across multiple call sites

### Follow-on cleanup: remove mutex-style `.lock` naming

- Rename mutex-style runtime files such as `work.lock`, `spawns.lock`, `sessions/*.lock`, and `active-primary.lock`
- Move advisory locking to hidden `.flock` sidecars or another internal-only path
- Reserve `.lock` for resolved developer-facing snapshot files such as `.meridian/agents.lock`

## 11. Success Criteria

The redesign is complete when all of the following are true:

- `meridian install ...` installs only into `.agents/`
- the current repo's `.agents/` fully determines what Meridian discovers
- the actual shipped `meridian-agents` content lives in the submodule, not only in local drafts
- source kinds are adapter-based (`git`, `path`) rather than GitHub-specific special cases
- installable content is discovered directly from source layout without requiring a Meridian-specific source manifest
- no home-directory agent/skill search paths affect behavior
- no `.claude` writes happen during install/update/remove
- no temp materialized agent/skill copies are needed
- Python code contains bootstrap/install recipes, not live default profile definitions
- the remaining interfaces and names match the new install/source model; dead sync/materialization vocabulary is gone
- core Meridian orchestration commands can bootstrap the configured default primary/subagent when required
- failures in that bootstrap affect only commands that need core agents, not the entire CLI
