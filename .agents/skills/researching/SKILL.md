---
name: researching
description: Explores codebases and evaluates approaches before planning. Use when investigating a problem space, comparing alternatives, or gathering context for a plan.
---

# Research

Explore the codebase, research best practices, evaluate alternatives, and recommend the best solution with clear reasoning.

## Key Constraints

- **Read project instructions first** — `CLAUDE.md` or `AGENTS.md` at repo root, plus stack-specific files.
- **Search before suggesting** — check if something already exists before recommending new implementations.
- **Evaluate 2-3 approaches** — describe each, compare pros/cons specific to this codebase, and recommend one.
- **Justify with WHY** — every recommendation needs reasoning tied to the specific codebase, not generic advice.
- **Be specific** — include file paths, function names, line numbers. Vague findings aren't useful.

## Output

Produce a report with these sections:

- **Problem Statement**
- **Codebase Context** — existing patterns, utilities, integration points (with file paths)
- **Best Practices** — industry recommendations with sources
- **Alternative Approaches** — 2-3 approaches with description, pros, cons, codebase fit
- **Recommendation** — which approach and WHY it fits this codebase
- **Open Questions**
