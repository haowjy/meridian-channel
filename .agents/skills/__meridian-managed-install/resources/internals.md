# Install System Internals

## Lock File (`agents.lock`)

The lock file is a JSON file tracking the resolved state of all managed sources and installed items. It is generated — do not edit manually.

### Structure

```json
{
  "version": 1,
  "sources": {
    "source-name": {
      "kind": "git|path",
      "locator": "URL or path",
      "requested_ref": "branch/tag/commit or null",
      "resolved_identity": { "commit": "full-sha" },
      "items": {
        "agent:name": { "path": "agents/name.md" },
        "skill:name": { "path": "skills/name/SKILL.md" }
      },
      "realized_closure": ["agent:name", "skill:name"],
      "installed_tree_hash": "sha256:...",
      "installed_at": null
    }
  },
  "items": {
    "agent:name": {
      "source_name": "source-name",
      "source_item_id": "agent:name",
      "destination_path": ".agents/agents/name.md",
      "content_hash": "sha256:..."
    }
  }
}
```

### Key Properties

- **`resolved_identity`**: For git sources, the exact commit SHA. Enables deterministic `update` without re-resolving.
- **`content_hash`**: SHA256 of normalized content. Used to detect local modifications and upstream changes.
- **`realized_closure`**: The full set of items installed from a source after filtering.

## Conflict Resolution

The engine compares three states: **source** (upstream content), **lock** (last installed state), **local** (on-disk files).

| Source vs Lock | Lock vs Local | Action |
|---------------|---------------|--------|
| Same | Same | `skipped` — nothing to do |
| Changed | Same | `updated` — apply upstream change |
| Changed | Changed | `kept` — local modifications preserved (use `--force` to override) |
| Same | Changed | `kept` — local modifications preserved |
| New | N/A | `installed` — fresh item |
| Removed | Same | `removed` — clean up |
| Removed | Changed | `kept` — local modifications preserved |
| N/A | N/A (unmanaged exists) | `conflict` — destination occupied by unmanaged file |

With `--force`, `kept` and `conflict` become `reinstalled` — local content is overwritten.

## Content Hashing

- Algorithm: SHA256
- Normalization: CRLF → LF, ensure trailing newline
- Agents: single-file hash
- Skills: composite tree hash of all files in the skill directory

## Concurrency

- Advisory locking via `fcntl.flock` on `.meridian/agents.lock`
- All state writes use atomic tmp+rename
- Safe for parallel processes reading the same lock

## Bootstrap

At runtime, Meridian auto-installs required default agents (`__meridian-orchestrator`, `__meridian-subagent`) if they're missing locally. The bootstrap:

1. Checks if the required agent exists on disk
2. If missing, looks for it in the lock file or manifest
3. If not found anywhere, adds the `meridian-agents` well-known source to `agents.toml`
4. Runs a targeted reconcile to install the missing items

Bootstrap only triggers for built-in Meridian agents. Custom agents that are missing at runtime fail immediately — install their source first.

## Well-Known Source Aliases

Currently registered:

| Alias | Expands To |
|-------|-----------|
| `meridian-agents` | `https://github.com/haowjy/meridian-agents.git` (ref: `main`) |

The CLI also auto-expands GitHub shorthand: `owner/repo` becomes `https://github.com/owner/repo.git`.

## Caching

Git sources are cached under `.meridian/cache/`:

- `cache/git/<source-name>/` — full git clones (preferred)
- `cache/archive/<source-name>/` — GitHub API archive fallback (when git binary unavailable)

Caches are reused across `update` and `upgrade` operations. `upgrade` fetches new commits into the cached clone.
