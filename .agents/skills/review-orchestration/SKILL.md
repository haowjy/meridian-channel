---
name: review-orchestration
description: How to direct reviewers effectively — choosing focus areas, selecting models, synthesizing findings, and calibrating review effort. Use when you're about to fan out reviewers and need to decide what perspectives to ask for, which models to use, and how to handle the results.
---
# Review Orchestration

You're the orchestrator, not the reviewer. Your job is to direct reviewers toward what matters, pick models that give you useful diversity, and synthesize the results into action.

## Choosing Focus Areas

The change itself tells you what review perspectives matter. Think about what could go wrong that testing won't catch:

- **Concurrent state** — if the code shares mutable state between threads, processes, or async tasks, ask a reviewer to focus on races, deadlocks, and ordering assumptions.
- **User input and trust boundaries** — if the code handles external input, authentication, or authorization, ask for security focus. Think about what an attacker could abuse.
- **Module structure and abstractions** — if the code restructures responsibilities, changes interfaces, or introduces new abstractions, ask for architectural review. Does this set up the next phase or paint it into a corner?
- **Correctness and contracts** — if the code implements tricky logic, state machines, or cross-module contracts, ask a reviewer to trace the critical paths and verify invariants.
- **Design alignment** — if there's a design doc, ask a reviewer to check for drift. Does the implementation match the intended approach, or has it silently diverged?

You don't need all of these on every change. A simple internal refactor might just need one reviewer looking at structural quality. A new auth flow might need security and concurrency reviewers. Match the focus to the risk.

## Model Selection

Focus areas are the primary review lever — multiple reviewers on the strongest model, each looking at different things (security, design quality, correctness), surfaces more issues than running the same review prompt on different models. Each focus area catches things the others miss because the reviewer is primed to think about different failure modes.

- **Strongest available model** — use for focused deep review: security, SOLID, correctness, architectural judgment. Fan out multiple reviewers with different focus areas for high-risk changes.
- **Fast/cheap model** — use for papercut passes: naming, style, obvious issues. Quick and cheap in parallel with the deep reviews.
- **Model diversity** — valuable as a tiebreak when reviewers disagree, or for a high-level sanity check from a different perspective.

Check your project config (CLAUDE.md, agent profiles) for current model assignments — these shift as model capabilities evolve. A fast reviewer that catches the obvious issues in 30 seconds is more valuable than a deep reviewer that takes 5 minutes to say the same thing. Save depth for where it matters.

## Review Agents

Different agents serve different review purposes — pick the right one for what you need:

- **reviewer** — adversarial code analysis. Specify a focus area in the prompt (security, SOLID, correctness, design alignment) for depth, or leave broad. Read-only — finds problems, doesn't fix them. Pass artifacts via `-f` and session context via `--from`.
- **refactorer** — structural improvement. Identifies and executes SOLID fixes, renames, extractions, dependency cleanup. Spawn after implementation phases or when reviewers flag structural debt. Reduces entropy so future agents work more effectively.
- **verifier** — build health gate. Runs tests, type checks, lints. Fixes mechanical breakage (import typos, missing annotations), reports substantive failures back.
- **investigator** — root-cause triage. Spawn when a test fails unexpectedly or a reviewer flags something that needs deeper analysis. Quick-fixes if small, files GH issues if larger, confirms non-issue if not real.

A typical review round might fan out a reviewer with a correctness focus, a reviewer with a design focus, and a verifier — all in parallel.

## Synthesizing Findings

If a reviewer found something valid, fix it. Agents are cheap — spawning a coder or refactorer to fix a style issue costs seconds, not hours. Don't create a backlog of deferred paper cuts that never get addressed. The only findings to skip are ones the reviewer got wrong (misunderstood the intent, flagged something that's actually correct).

When reviewers disagree, you have context they don't — you've been managing the work, you know the design intent, you know what's coming in the next phase. Make a call and record it in `$MERIDIAN_WORK_DIR/decisions.md`. If the outcome changes approved architecture direction, update the relevant docs in `$MERIDIAN_WORK_DIR/design/` too. If you're genuinely uncertain, escalate to the user.

Cap review rounds at two for design and three for implementation. If it's still not converging, the issue is structural — more review won't fix it.

## Calibrating Effort

Scale review to the risk:

- **Low risk** (internal refactor, well-tested area, small blast radius) — one reviewer, fast model, quick pass.
- **Medium risk** (new feature, moderate complexity) — two reviewers with different focus areas.
- **High risk** (security-sensitive, concurrent, cross-cutting, public API changes) — two or three reviewers on the strongest model with different focus areas. A fast model handles a papercut pass in parallel.

The goal is confidence that the change is sound, not maximum review coverage. When you have enough signal to act, stop reviewing and move forward.
