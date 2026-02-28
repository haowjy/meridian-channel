---
name: scratchpad
description: Conventions for disposable scratch code and verification scripts. Use when writing smoke tests, quick probes, or temporary artifacts during task execution.
user-invocable: false
---

# Scratchpad

Disposable code and artifacts live in `.scratch/`, either in the working directory or under a designated output directory. Never committed.

## Smoke Tests

Any disposable code used to quickly verify something works. Write them liberally after implementing changes.

| Type | When to use | Example |
|------|-------------|---------|
| **Logic verification** | Verify guard patterns, state machines, edge cases | `vitest` test asserting a staleness guard rejects stale responses |
| **API/endpoint probes** | Verify endpoints respond correctly | `curl` scripts hitting local dev server |
| **Integration checks** | Verify two systems work together | Script that creates a resource then reads it back |
| **Regression probes** | Verify a specific bug is fixed | Minimal repro of the bug, now passing |

- **Promote** to committed unit tests when a smoke test catches a real issue

## Rules

- Write scratch code to `.scratch/` — never commit it
- Do not store secrets or raw tokens (`.env` values, JWTs, API keys, cookies)
- Check project instruction files (`CLAUDE.md` or `AGENTS.md`) for auth token scripts and API base URL
- Name files descriptively: `{feature}-{what}.test.ts` or `{endpoint}.sh`
- Use the project's existing test runner (vitest, jest, etc.) for logic smoke tests

## Notes

Write markdown notes as you work — findings, decisions, progress. Notes persist on disk across context clears.

Use the co-located script:

```bash
# Write a quick note (auto-named with timestamp)
scripts/scratch.sh write --tag research -p "Found that X uses Y pattern"

# Write from stdin
echo "curl returned 200" | scripts/scratch.sh write --tag probe

# Explicit file path within session
scripts/scratch.sh write my-test.sh -p "#!/bin/bash\necho test"

# List notes from current session
scripts/scratch.sh list

# Read latest note
scripts/scratch.sh read @latest

# List all sessions
scripts/scratch.sh list --all
```

When run via run-agent, session defaults to the run ID. Standalone, pass `--session` or let it auto-bucket by date.
