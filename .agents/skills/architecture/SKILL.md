---
name: architecture
description: Architecture design methodology — problem framing, tradeoff analysis, and approach evaluation. Use this whenever designing a system, component, or significant change — including when the user says "let's think about how to build X", "how should we architect this", or describes a non-trivial feature, refactor, or system change.
---

# Architecture Design

## Frame the problem before proposing solutions

When someone opens with a solution, identify the real pain first: goals, constraints, and failure modes. A design cannot be judged without a clear problem statement.

## Explore multiple approaches before committing

The first plausible approach is often not the best one. Surface hidden constraints, propose alternatives, and compare them on the dimensions that matter for this work.

## Make tradeoffs explicit

For each approach, spell out benefits, risks, and operational consequences. Prioritize tradeoffs tied to real constraints (performance, reliability, complexity, delivery risk), not generic pros/cons.

## Stress-test the selected approach

Before implementation, review the chosen direction against feasibility and integration risk. Ask focused reviewers to dig into specific concerns rather than broad shallow scans.

Common areas: **feasibility** (can this actually be built as described?), **scope boundaries** (is it clear what's in and out?), **integration risks** (how does this connect to existing systems?), **scalability**, **security implications**, **migration path** (if changing existing behavior, how do you get from here to there?), **alternative approaches** (were other options considered?), and **testability**. But these are starting points — add domain-specific dimensions when the design calls for it.

Not every area applies to every design. Pick the ones that matter and tell each reviewer where to dig.
