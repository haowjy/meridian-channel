# Review: Design Alignment & Framing

You are reviewing the design package for **workspace-config-design** (boundary clarity across Meridian + Mars on-disk state, with a local `workspace.toml` for context-root injection). Artifacts are attached via `-f`.

## Your Focus Area: Design Alignment

Other reviewers are covering correctness/migration, UX, refactor structure, and external prior art. Stay in this lane and go deep.

## Core Questions

1. **Requirements → spec coverage.** For each goal G1–G8 and each constraint in `requirements.md`, is there at least one EARS statement in `design/spec/workspace-config.md` that demonstrably satisfies it? Call out goals/constraints with no anchor, or anchored only by ambiguous statements.

2. **Spec → requirements grounding.** Is every EARS statement traceable back to a requirement or explicit non-goal? Flag statements that have drifted into out-of-scope territory, especially around CLI surface (WS-4) and REF-1.

3. **Supersession of the prior design (D11).** The decisions log says the prior workspace-only design is superseded. Verify: does the revised package actually re-frame around boundary clarity (G1, G7, D2, D12), or does it still read as a workspace-only design with extras bolted on? If the reframing is incomplete, name the specific places where it leaks.

4. **Internal consistency.** Cross-check spec ↔ architecture ↔ decisions. In particular:
   - OWN-1.5 (models move to repo root) vs D8 (models stays separate) vs architecture §"Models Integration" Option B recommendation — are these coherent across all three?
   - CFG-1.3/CFG-1.4 (migrate command, remove `!config.toml` exception) vs architecture §"Gitignore Simplification" vs feasibility Probe 8 — is the deprecated-lines mechanism referenced consistently?
   - WS-3.4 (workspace injected BEFORE passthrough for last-wins) vs architecture §"Context-Root Injection Architecture" — does the stated ordering match the "last-wins" claim?

5. **Non-goal discipline.** Review requirements' "Non-Goals (First Version)". Does the spec sneak any of them back in (per-harness subsets, workspace settings, fs/work migration, shareable team workspace, auto-detection)?

6. **FUT-1 markers as design hygiene.** FUT-1.1–3 document intent without requiring implementation. Are any of them actually load-bearing for v1 correctness and should be promoted to real statements? Or are there future concerns not marked that should be?

## Output Format

Use the `review` skill structure. For every finding, give a severity (blocker / major / minor / nit), a concrete pointer (file + statement ID or section), and a recommended resolution. Prefer fewer substantive findings over a long list of nits.

End with a verdict:
- `converged` — no blockers or majors, ready to proceed.
- `revise` — blockers or majors present; summarize the smallest set of edits that would unblock.

Do not edit artifacts. Read-only review.
