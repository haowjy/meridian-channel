# Managed Sources Smoke Notes

Use this reference when validating `meridian sources`.

## What Sources Does

`meridian sources` manages external skills and agents from local paths or git repos. The core operations:

- **install** — resolves a source, materializes its skills into `.agents/skills/` and agents into `.agents/agents/`, records the source in `.meridian/agents.toml` or `.meridian/agents.local.toml`, and writes snapshot data to `.meridian/agents.lock`
- **update** — re-resolves each declared source, diffs against the lock, and re-materializes changed items
- **uninstall** — removes managed files plus manifest and lock entries for one source
- **status** — compares current materialized state against lock entries, reports in-sync or drift

Key implementation files live under `src/meridian/lib/install/` plus `src/meridian/cli/install_cmd.py`.

## Minimum Bar

- Run `tests/smoke/quick-sanity.md`
- Run `tests/smoke/install/install-cycle.md`
- Verify both CLI output and the resulting `.agents/`, `.meridian/agents.toml` or `.meridian/agents.local.toml`, and `.meridian/agents.lock` state

## When To Go Beyond the Local Round Trip

The local-path cycle is enough for many source-management changes, but it does not exercise remote clone and fetch behavior.

If your change touches:

- remote source resolution (GitHub slug → clone → tree walk)
- lock semantics (hash comparison, conflict detection)
- repo-vs-path source branching in `resolve_source()`
- shared-vs-local manifest routing (`agents.toml` vs `agents.local.toml`)

also run one real remote-source install, not just a local-path round trip.

## Edge Cases to Watch

- **Missing source** — install from a path/repo that doesn't exist should fail cleanly, not crash
- **Already-installed source** — re-installing the same source name should either skip or reinstall, never duplicate
- **Orphaned files** — if a source previously installed 3 skills but now only has 2, the removed skill should be cleaned up on update
- **Lock drift** — manually editing files under `.agents/` should cause `status` to report drift, not silently pass

## What To Inspect

Do not stop at command success. Check:

- installed files under `.agents/`
- configured source entries in `.meridian/agents.toml` and `.meridian/agents.local.toml`
- item snapshots and source metadata in `.meridian/agents.lock`

The concrete command sequence lives in `tests/smoke/install/install-cycle.md`.
