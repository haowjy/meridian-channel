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

Different models catch different things. Use this to your advantage:

- **Strong reasoning models** (gpt-5.4, opus) — good for deep analysis, security review, subtle correctness issues, and architectural judgment. Use when the stakes are high or the code is complex.
- **Fast models** (gpt-5.3-codex) — good for quick structural reviews, style consistency, obvious issues. Use when you need a fast pass or the change is low-risk.
- **Model diversity** — running the same review prompt on two different models surfaces blind spots. Each model family has different strengths and biases. When a review matters, spawn the same focus area on two models and compare what they find.

Don't always reach for the strongest model. A fast reviewer that catches the obvious issues in 30 seconds is more valuable than a deep reviewer that takes 5 minutes to say the same thing. Save depth for where it matters.

## Synthesizing Findings

When multiple reviewers report back, synthesize by severity:

- **Critical** — blocks progress. Fix before moving on.
- **High** — the orchestrator decides: fix now, or defer with explicit rationale in the design doc.
- **Medium/Low** — log if useful, move on. Spawn an investigator for anything worth tracking but not worth stopping for.

When reviewers disagree, make a call. You have context they don't — you've been managing the work, you know the design intent, you know what's coming in the next phase. Record the decision and move on. If you're genuinely uncertain, escalate to the user.

Cap review rounds at two for design and three for implementation. If it's still not converging, the issue is structural — more review won't fix it.

## Calibrating Effort

Scale review to the risk:

- **Low risk** (internal refactor, well-tested area, small blast radius) — one reviewer, fast model, quick pass.
- **Medium risk** (new feature, moderate complexity) — two reviewers with different focus areas.
- **High risk** (security-sensitive, concurrent, cross-cutting, public API changes) — two or three reviewers on strong models, consider model diversity for a second opinion.

The goal is confidence that the change is sound, not maximum review coverage. When you have enough signal to act, stop reviewing and move forward.
