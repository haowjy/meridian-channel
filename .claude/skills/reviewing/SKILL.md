---
name: reviewing
description: Reviews code against project rules and curated reference files. Use when auditing files for violations, reviewing changes, or generating cleanup tasks.
---

# Code Review

Review code against curated project rules and flag all violations found — not just things introduced by recent changes.

## Rules Loading

1. **Always** load `references/general.md`
2. **Read project instruction files** — `CLAUDE.md` or `AGENTS.md` at repo root, plus stack-specific files relevant to the scope.
3. **Load matching reference files** — if `references/<dir>.md` exists for a top-level directory in scope, load it.

## Categories

1. **Correctness** — logic errors, edge cases, off-by-one
2. **Security** — hardcoded secrets, injection risks, missing auth checks
3. **Reliability** — error handling, race conditions, resource cleanup
4. **Architecture** — SOLID violations, import boundaries, coupling
5. **Dead code & Complexity** — unused code/imports, premature abstractions
6. **Project conventions** — violations of loaded rule files

## Output

Produce a report grouped by category. For each issue: file, location, what's wrong, why, and suggested fix.
