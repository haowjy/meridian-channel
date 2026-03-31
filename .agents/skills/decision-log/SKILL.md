---
name: decision-log
description: Decision capture methodology — reasoning, alternatives, and constraints. Use whenever you're making design choices, weighing alternatives, synthesizing review feedback, adapting plans during implementation, or rejecting an approach — any moment where "we chose X over Y" needs to survive beyond this conversation.
---
# Decision Log

Decisions evaporate. The reasoning behind a choice — why this approach, what alternatives were rejected, what constraints forced the tradeoff — lives in conversation context that gets compacted, in sessions that end, in heads that move on to the next task. A month later, someone asks "why did we do it this way?" and the answer is gone.

Record decisions while the reasoning is fresh. Not retroactively, not in a batch at the end — in the moment you make the choice. The best time to capture a decision is when you're still holding the alternatives in your head and can articulate why one won.

## What to Record

Every decision entry answers three questions: **what** was decided, **why** it was chosen, and **what else** was considered.

- **The choice itself.** State it concretely — name the files, interfaces, patterns, or behaviors affected. "We decided to use an event-based approach" is vague. "Session state uses append-only JSONL events instead of mutable JSON files" is a decision.
- **The reasoning.** What constraints, evidence, or goals drove the choice? Link to design docs, benchmarks, or code that informed it. Reasoning without evidence is opinion.
- **Alternatives rejected.** Name them and say why. "We considered X but rejected it because Y" is the most valuable sentence in any decision record — it prevents the next person from reliably re-proposing X.
- **Constraints discovered.** Often the decision itself is less interesting than the constraint that forced it. "The harness API doesn't support streaming" explains more than "we chose polling."
- **What changed.** If this decision revises a prior one, reference what it replaces and why circumstances shifted.

## When to Record

Capture decisions at the moment they happen, not after the fact:

- **During design exploration** — when evaluating approaches, choosing between architectures, or settling on abstractions. This is where the highest-value decisions live and where alternatives are most clearly articulated.
- **After review synthesis** — when triaging reviewer findings, deciding what to fix, what to defer, and what to reject. Especially when overruling a reviewer — record why.
- **During implementation pivots** — when the plan meets reality and something changes. The spec said one thing, the code demands another. Capture the adaptation and the evidence that forced it.
- **At phase boundaries** — when handing off between phases, summarize the key decisions that shaped the output. The next agent needs to know what was chosen, not re-derive it.

Do not batch decisions retroactively. A decision log written from memory after a long implementation session will miss the nuance — the alternatives blur together, the constraints lose their specificity, the reasoning flattens into post-hoc justification.

## How to Structure Entries

Structure entries so they're searchable and traceable:

- **Timestamp and context.** When was this decided, and during what phase or task?
- **Concrete references.** Use file paths, function names, and line numbers — not abstractions. "The spawn store" is searchable only if you already know what it is. `src/meridian/lib/state/spawn_store.py` is findable by anyone.
- **Link to source material.** Point to the design doc section, review finding, or code that motivated the decision. Decisions without provenance are assertions.
- **One decision per entry.** Bundling multiple choices into one entry makes each one harder to find and reference later.

## Decision Types

Different contexts produce different kinds of decisions. Recognize which type you're recording:

**Design decisions** — architecture choices, data model tradeoffs, API surface decisions, pattern selection. These have the longest shelf life and the highest cost if lost. Record them with full alternative analysis.

**Execution decisions** — implementation pivots, spec adaptations, scope adjustments made when the plan meets the codebase. These explain why the implementation diverged from the design. Reference both the original plan and the evidence that forced the change.

**Review decisions** — triage choices about what to fix now, what to defer, and what to reject. These are especially important when overruling reviewers or deferring known issues. Record the severity assessment, the reasoning, and any conditions under which the deferred item should be revisited.

## What Makes a Decision Worth Recording

Not every micro-choice needs an entry. Record a decision when:

- Someone could reasonably make a different choice (if there's only one viable option, that's a constraint, not a decision)
- The reasoning isn't obvious from the code itself (if the code makes the "why" self-evident, a decision entry adds noise)
- Future agents or humans will encounter this code and wonder why (the test: would you want this context if you were reading this code for the first time?)
- You're overruling, deferring, or reversing something (these always need explanation)

Skip boilerplate decisions that follow directly from project conventions. The goal is a useful record of non-obvious choices, not a comprehensive log of everything that happened.
