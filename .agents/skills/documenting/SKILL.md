---
name: documenting
description: Keep docs in sync with code changes. Use after implementing a phase or feature, after a refactor, or whenever code changes might have made documentation stale. Covers design docs, READMEs, API contracts, architecture overviews, code comments, and inline examples. Also use when the orchestrator asks you to check for documentation drift.
---

# Documenting

Documentation drift is expensive to fix later and invisible until it misleads someone. Your job as a documenter is to triage what drifted and fix what you can, fast.

The key insight: **discovery is a search problem, writing is a quality problem**. They need different models. Don't conflate them.

## The Two-Pass Pattern

### Pass 1 — Discovery (cheap model, e.g. haiku)

Scan changed files, find all docs that reference them. This is fast, broad, mechanical work — a strong model is overkill here and wastes budget.

**What to look for:**

Given a set of changed source files, search the docs for:
- Function/method names that appear in the changed files
- Module paths and import names
- Config keys, env vars, CLI flags
- Component or class names
- Any prose that describes behavior you can see changed in the diff

Cast wide. It's better to flag a doc that doesn't need updating than to miss one that does.

**Output from Pass 1:**

Produce a structured list, one entry per affected doc:

```
## Affected docs

### docs/architecture.md
- References `SpawnExecutor` class — renamed to `SpawnRunner` in src/runner.py
- Architecture diagram shows old 3-tier layout, new component `StateManager` not depicted

### README.md
- Setup step references `pip install` — project now uses `uv sync`
- Usage example calls `meridian run` — command is now `meridian spawn`

### No changes needed
- docs/api/events.md — checked, event schema unchanged
- docs/contributing.md — no references to changed files
```

This list is what the orchestrator hands to Pass 2.

### Pass 2 — Writing (quality model, e.g. opus)

Given the Pass 1 output and the affected doc files, update what you can and flag what needs human/orchestrator attention.

Writing good docs is hard. Don't rush it. Read the surrounding context before making changes — a function rename might need a paragraph rewrite, not just a find-replace.

## What to Update vs. What to Flag

### Update directly

Small, self-contained fixes where the right answer is obvious:

- Renamed function in a code example
- Updated parameter names or types
- Corrected CLI flag or command syntax
- Fixed import paths
- Typo or stale file path in prose

Make these changes. Don't ask permission.

### Flag for the orchestrator

Structural changes where the right answer isn't obvious from the code alone:

- New section needed that doesn't exist yet (you'd be inventing content, not correcting it)
- Architecture diagram that needs redesign — topology changed, not just a renamed node
- API docs that need full rewrite because the API contract changed substantially
- Conceptual prose that may be wrong but requires domain judgment to fix correctly
- Multiple docs that conflict with each other — resolving that requires a design decision

For flags, write a clear note: what's wrong, what the doc currently says, what the code now does, and why you're not fixing it yourself. The orchestrator decides whether to prioritize it.

## Anatomy of a Good Doc Update

Before editing, read:
1. The changed source file (or the diff)
2. The full section of the doc you're updating, not just the stale line

Then write:
- Match the existing voice and style of the document
- Don't over-explain. If a function renamed, update the name — don't add a paragraph about the rename
- Keep examples runnable. Verify that code examples actually reflect the current API
- If you're unsure about behavior, say so explicitly in your flag rather than guessing

## What to Check in Each Doc Type

**Design docs / architecture overviews**
- Does the described system still match the implementation?
- Are new components mentioned that aren't in the overview?
- Are removed components still documented as if they exist?

**READMEs**
- Setup steps (install commands, env vars, prerequisites)
- Usage examples (command syntax, flag names, output format)
- Configuration reference (keys, defaults, types)

**API / module docs**
- Function signatures (parameters, return types, exceptions)
- Deprecated functions still documented without a deprecation notice
- New public functions missing from the docs entirely

**Code comments**
- Comments referencing removed or renamed symbols
- Comments that describe behavior that changed
- TODOs referencing things that were already done

**Inline examples**
- Import paths that no longer resolve
- Method calls with wrong argument counts or names
- Output examples that don't match current behavior

## Output Format

Always produce a summary of what you did, structured as:

```
## Documentation update summary

### Updated
- `docs/architecture.md` — Updated component name SpawnExecutor → SpawnRunner, added StateManager to component list
- `README.md` — Fixed install command (pip → uv sync), updated `meridian run` → `meridian spawn` in usage example

### Flagged for review
- `docs/design/state-machine.md` — State diagram is substantially wrong after the StateManager refactor. Current diagram shows 4 states; implementation now has 7. Needs redesign, not a quick fix.
- `docs/api/spawn.md` — SpawnOptions interface changed significantly (3 new required fields). Full rewrite needed to be accurate.

### Examined, no changes needed
- `docs/contributing.md`
- `docs/testing.md`
```

This makes it easy for the orchestrator to see what happened without re-reading everything.

## How the Orchestrator Invokes This

```bash
# Pass 1 — discovery (cheap model)
meridian spawn -a documenter -m haiku \
  -p "Find all docs affected by the Phase 3 changes. Changed files: [list]. Output a structured list of affected docs and what drifted." \
  -f src/runner.py -f src/state.py

# Pass 2 — writing (quality model) — uses Pass 1 output
meridian spawn -a documenter -m opus \
  -p "Update these docs based on the discovery pass: [paste Pass 1 output]. Update what's obvious, flag what needs design judgment." \
  -f docs/architecture.md -f README.md -f docs/api/spawn.md
```

The orchestrator reads Pass 1 output to decide which docs are worth the Pass 2 cost. If Pass 1 finds nothing, skip Pass 2. If Pass 1 finds only minor fixes, a cheaper model might be fine for Pass 2 too — use judgment.

## When You're Doing Both Passes Yourself

If invoked without model constraints, do the discovery pass mentally first — scan broadly, build your list — then switch to careful writing mode. Don't interleave them. Finish the triage before you start editing.
