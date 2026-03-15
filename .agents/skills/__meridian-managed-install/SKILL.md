---
name: __meridian-managed-install
description: "Managed install system for syncing agent profiles and skills from external sources (git repos, local paths). Use when installing, updating, or removing managed sources, checking install drift, understanding agents.toml, or setting up a freshly cloned repo."
---

# Managed Install

Meridian's managed install system keeps `.agents/` in sync with external sources — git repos or local paths. Instead of manually copying agent profiles and skills into `.agents/`, declare where they come from and let the install engine handle reconciliation, conflict detection, and provenance tracking.

This matters because `.agents/` is the single discovery root for all agent profiles and skills. If content isn't there, agents can't find it. The install system is how content gets there reproducibly.

## Mental Model

Think of it like a package manager for agents and skills:

- **`agents.toml`** is your shared manifest — what sources you want, committed to version control
- **`agents.local.toml`** is your machine-local manifest — gitignored, for path sources or personal overrides
- **`agents.lock`** is the lock file — exact resolved versions for reproducibility
- **`.agents/`** is the install target — where content lands on disk

The engine compares source ↔ lock ↔ local to decide what to install, update, skip, or flag as conflicting. Local modifications are preserved by default (never silently overwritten).

## Commands

### Install a source

```bash
meridian sources install <source> [--name NAME] [--ref REF] [--agents a1,a2] [--skills s1,s2] [--rename OLD=NEW] [--local]
```

The CLI auto-detects source type:

```bash
meridian sources install meridian-agents                        # Well-known alias
meridian sources install myorg/team-agents --ref v1.2.0         # GitHub shorthand
meridian sources install https://github.com/org/repo.git --ref main  # Full URL
meridian sources install ./local-agents --name local            # Local path (auto-routes to agents.local.toml)
```

Without `--agents` or `--skills`, everything in the source is installed. Use filters when you only need specific items — this avoids polluting `.agents/` with content you don't want.

```bash
meridian sources install myorg/team-agents --agents reviewer,coder --skills reviewing
```

Rename items at install time with `--rename OLD=NEW` to avoid collisions. The `--rename` flag is repeatable. If the name has no `kind:` prefix, it defaults to renaming an agent:

```bash
meridian sources install myorg/team-agents --rename old-agent=new-agent          # Renames agent
meridian sources install myorg/team-agents --rename skill:old-skill=new-skill    # Renames skill
```

Use `--local` to force the source into `agents.local.toml` (gitignored) instead of the shared `agents.toml`. Path sources are automatically routed to `agents.local.toml`; git sources go to `agents.toml` by default.

### Restore from lock (install without source)

```bash
meridian sources install
```

Running `meridian sources install` with no source argument reinstalls from the locked state without re-resolving refs. Deterministic — running it twice produces identical results. Use this after cloning a repo (the lock file is committed, `.agents/` content might not be) or to reset managed files back to their locked state.

### Pull upstream changes (update)

```bash
meridian sources update [--source NAME]
```

Re-resolves floating refs (like `main`) to the latest commit, then installs. This is how you pull upstream improvements. Pinned refs (tags, commit SHAs) won't change — only branches advance. Use `--source` to update only a specific source.

### Check for drift (status)

```bash
meridian sources status
```

Compares lock file against on-disk content. Reports:

| Status | Meaning | Action |
|--------|---------|--------|
| `in-sync` | Local matches lock | Nothing needed |
| `locally-modified` | You edited a managed file | Decide: keep edits or `meridian sources install --force` to reset |
| `missing` | Lock says it should exist, but file is gone | `meridian sources install` to restore |
| `orphaned` | File exists but source is gone from lock | Remove manually or ignore |

### List installed sources

```bash
meridian sources list
```

Shows all configured sources and the agents/skills they provide. Output includes whether each source is local (from `agents.local.toml`) or shared (from `agents.toml`), and whether a shared source is overridden by a local entry.

### Uninstall items or sources

```bash
meridian sources uninstall <item-name> [<item-name> ...]   # Remove specific agents or skills
meridian sources uninstall --source <name>                  # Remove an entire source
```

To remove individual managed items (agents or skills) by name:

```bash
meridian sources uninstall my-agent                  # Removes the agent named my-agent
meridian sources uninstall my-agent my-skill         # Removes multiple items at once
```

To remove an entire source and all its managed files:

```bash
meridian sources uninstall --source team-agents      # Removes source and its files from .agents/
```

Without `--force`, locally modified files are kept — the engine won't silently destroy your edits.

### Common flags

All install commands accept:
- `--dry-run` — preview what would happen without writing anything
- `--force` — overwrite local modifications (use deliberately, not by default)

## Choosing the Right Command

| Situation | Command |
|-----------|---------|
| Fresh clone, need agents/skills | `meridian sources install` |
| Adding a new external source | `meridian sources install <source>` |
| Pulling latest from upstream | `meridian sources update` |
| Something seems wrong or drifted | `meridian sources status` |
| See what sources are configured | `meridian sources list` |
| Removing a specific agent or skill | `meridian sources uninstall <name>` |
| Removing an entire source | `meridian sources uninstall --source <name>` |
| Previewing before committing | Add `--dry-run` to any command |

## State Files

| File | Role | Edit? | VCS? |
|------|------|-------|------|
| `.meridian/agents.toml` | Shared source manifest | Yes — this is your config | Commit |
| `.meridian/agents.local.toml` | Machine-local source manifest | Yes — for path sources or personal overrides | Gitignored |
| `.meridian/agents.lock` | Resolved state | No — generated by the engine | Commit |
| `.meridian/cache/` | Git clone caches | No — managed automatically | Gitignored |

The shared manifest (`agents.toml`) is where you declare intent for the team. The local manifest (`agents.local.toml`) is for machine-specific sources like local paths. The lock file records what was actually installed. Both `agents.toml` and `agents.lock` should be committed to version control — the lock enables deterministic `meridian sources install` on other machines.

Path sources auto-route to `agents.local.toml` because absolute/relative paths are machine-specific. Git sources go to `agents.toml` by default. Use `--local` to override this routing.

Read [`resources/manifest-reference.md`](resources/manifest-reference.md) for the full `agents.toml` schema, item filtering, rename format, and source layout conventions.

Read [`resources/internals.md`](resources/internals.md) for lock file structure, conflict resolution logic, content hashing, bootstrap behavior, and caching.
