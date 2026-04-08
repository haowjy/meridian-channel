# Reviewers

@reviewers catch what testing can't — design drift, subtle correctness issues, architectural erosion. The value of multiple @reviewers comes from different focus areas and different models, not redundant coverage of the same concern.

Use @reviewer fan-out in two default places: design review and the final end-to-end implementation review loop. Intermediate implementation phases are tester-driven; @reviewers are escalation-only there.

Design review is the highest-leverage review point — catching a bad interface or missed constraint before anyone writes code saves entire implementation cycles.

## Default Lanes

These should be part of design review and the final implementation review loop unless there's a specific reason to skip:

@reviewer — adversarial code analysis with a specified focus area. Give each @reviewer a different focus area so you get breadth — the change itself tells you what perspectives matter. Common dimensions: correctness and contract compliance, concurrent state and races, security and trust boundaries, design alignment. Pick the ones that match what could actually go wrong with this specific change. Read-only.

@refactor-reviewer — structural review for tangled dependencies, mixed concerns, and coupling. Reports findings with recommended moves. Include this in design review and the final implementation review loop. Structural drift compounds silently across phases; catching it only at the end is expensive, but forcing structural fan-out in every intermediate phase spends review budget inefficiently. Read-only.

## Focus Areas

The change tells you what perspectives matter. Think about what could go wrong that testing won't catch:

- **Correctness and contracts** — does the code do what it claims? Are invariants maintained?
- **Concurrent state and races** — shared mutable state, lock ordering, TOCTOU
- **Security and trust boundaries** — input validation, privilege escalation, injection vectors
- **Design alignment** — does the implementation match the spec? (Always include this one)
- **Module structure** — covered by @refactor-reviewer as a default lane

Not all apply to every change. The goal is matching review perspectives to actual risk, not checking every box.

## Intermediate-Phase Escalation

During intermediate implementation phases, involve @reviewers only when testers surface a concrete behavioral issue the @coder cannot resolve confidently. Keep escalation scoped:

- Assign one @reviewer to the specific unresolved concern.
- Add a second @reviewer only if the issue spans multiple risk dimensions.
- Feed @reviewer findings back into @coder + tester loops, then continue phase execution.

## Synthesizing Findings

Fix valid findings — agents are cheap. The only findings to skip are ones the @reviewer got wrong. When @reviewers disagree, the orchestrator has context they don't — the full design, prior phases, runtime discoveries. Make the call and record it in the decision log.

If reviews aren't converging after multiple iterations, that's usually a signal the design has a structural problem — investigate or escalate rather than forcing convergence.
