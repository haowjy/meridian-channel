---
name: __meridian-install
description: Managed install system for syncing agent profiles and skills from external sources (git repos, local paths). Use when installing, updating, or removing managed sources, checking install drift, understanding agents.toml, or setting up a freshly cloned repo.
---

# Managed Install

Meridian keeps `.agents/` in sync with external sources declared in `agents.toml`. All commands live under `meridian sources` — `install`, `update`, `status`, `list`, `uninstall`.

## Installing

```bash
meridian sources install <source> [--agents a1,a2] [--skills s1,s2]
```

Source addressing:
- `./path` or `~/path` — local directory
- `@owner/repo` — GitHub shorthand
- `https://github.com/org/repo.git --ref main` — full URL with optional ref

Without `--agents`/`--skills`, everything is installed. Agent skill dependencies are auto-resolved from frontmatter.

**Bare install** (no source arg) syncs from the lock file — use after cloning a repo:

```bash
meridian sources install
```

## Drift Detection

`meridian sources status` compares lock vs on-disk:

| Status | Meaning |
|--------|---------|
| `in-sync` | Matches lock |
| `locally-modified` | You edited a managed file |
| `missing` | Expected by lock but gone — bare install to restore |
| `orphaned` | File exists but source removed from lock |

## State Files

| File | Commit? | Edit? |
|------|---------|-------|
| `.meridian/agents.toml` | Yes | Yes — source manifest |
| `.meridian/agents.lock` | Yes | No — generated |
| `.meridian/agents.local.toml` | No | Yes — personal overrides (`--local` flag) |

Read [`resources/manifest-reference.md`](resources/manifest-reference.md) for the full `agents.toml` schema, filtering, renames, and source layout.
