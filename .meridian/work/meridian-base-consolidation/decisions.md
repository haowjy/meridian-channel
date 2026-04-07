# Decision Log — meridian-base Skills Consolidation

## D1 — Skill name: `__meridian-cli`, not `__meridian`

**Decision:** Name the new singular CLI reference skill `__meridian-cli`.

**Why:** The user explicitly asked for `__meridian-cli` in the spawning prompt. Beyond user preference, the name makes the scope unambiguous: this skill teaches the CLI surface and the principles behind it. Reserving `__meridian` (without the suffix) leaves room for a future skill that teaches meridian's broader runtime model — e.g., the harness adapter abstraction, the spawn lifecycle state machine, the JSONL event schema — at a different altitude. Conflating "the CLI" with "meridian as a system" would force one skill to do two altitudes badly.

**Rejected:** `__meridian` (the issue's original name) — ambiguous in a way that would re-emerge later.

## D2 — Split `__meridian-session-context` rather than fold-and-leak

**Decision:** Delete `__meridian-session-context` from base. Move CLI-reference content into `__meridian-cli`. Move workflow content into a new dev-workflow skill.

**Why:** The skill currently does two unrelated jobs. Folding the whole thing into `__meridian-cli` keeps the cross-layer leak — `__meridian-cli` would inherit `@explorer` references. Leaving it in base unchanged keeps the leak too. Splitting honors the layer boundary and lets each half live where its assumptions are valid.

**Rejected:**
- *Fold whole thing into `__meridian-cli`.* Leaks `@explorer` into base.
- *Leave it in base, drop the `@explorer` references.* The workflow guidance becomes vague — "delegate to a cheap exploration spawn" is true but loses the concreteness that makes it actionable. The pattern is real workflow knowledge and deserves a real home.
- *Move whole thing to dev-workflow.* Then base loses the CLI reference for `meridian session ...`, forcing every base-level user to learn it ad-hoc from `--help`. That's actually fine for a sufficiently rich `--help`, but the consolidation is more legible if `__meridian-cli` covers the whole CLI surface uniformly.

## D3 — New dev-workflow skill name: working title `session-mining`, planner finalizes

**Decision:** Use `session-mining` as a working name in the design. The planner picks the final name in phase 1.

**Why:** Naming this well requires balancing several constraints — it's not "session reading" (too narrow), not "context recovery" (too broad), not "transcript mining" (right shape but odd phrasing). `session-mining` captures the workflow it teaches without locking the planner out of a better choice. Nothing in the design depends on the specific name beyond consistency, so deferring is cheap.

**Alternatives noted in passing:** `session-context` (too close to the deleted base skill — confusing), `transcript-mining` (correct but jargon-flavored), `context-recovery` (broader than the actual skill).

## D4 — Generic-guidance vs example reference policy

**Decision:** In base skills, dev-workflow agent names like `@reviewer` are allowed inside *examples* that illustrate a concept, but not inside *generic guidance* that prescribes behavior. The test: if you delete the agent name and the sentence still makes sense as a prescription, it was generic guidance — rewrite. If the sentence becomes meaningless, it was an example — keep.

**Why:** Examples lose their pedagogical value when stripped of concrete names. "An agent profile that scopes tools narrowly" is true but forgettable; "A `@reviewer` profile that scopes tools to `git diff` and `cat`" is memorable. The skill is still correct in a project without dev-workflow — the reader just doesn't have that specific profile to look at, but the concept transfers. Generic guidance is different: "fan out @reviewers" tells the reader to do something, and that something is broken without dev-workflow.

**Rejected:**
- *Forbid all dev-workflow agent names in base.* Strips legitimate examples and weakens `agent-creator` / `skill-creator`.
- *Allow them everywhere.* Lets generic guidance leak silently.

This policy gets codified as a paragraph in both `agent-creator/anti-patterns.md` and `skill-creator/anti-patterns.md` so the next sweep knows the rule.

## D5 — `--help` text fixes are prerequisite, not concurrent

**Decision:** The plan executes `--help` expansions *before* deleting the old skills.

**Why:** The new `__meridian-cli` skill points agents at `--help` as the canonical reference. If an agent loads the new skill while the help text is still thin, it lands on inadequate content and either fails or fabricates. Doing help-text expansion first means the consolidation never has a window where references are broken.

**Rejected:** *Concurrent* — the old skills cover the gaps so it doesn't matter what order things land. Wrong: the old skills go away in the same plan, and there's no guarantee the plan executes phases atomically across an interrupted session. Sequencing is cheap insurance.

## D6 — Slim `--help`-duplicating content, don't gut it

**Decision:** Sections in `__meridian-cli` that touch a CLI surface use a one-paragraph overview + a single `--help` pointer. They do *not* enumerate flags, even where the old skill did. Exception: tables that capture *patterns* (failure-mode → first move, env-var → purpose) stay because `--help` doesn't teach those.

**Why:** The point of consolidation is fewer lines, not the same lines redistributed. Re-documenting flags here defeats the purpose and creates the same drift problem we're solving. The failure-mode table in particular survives because reading "exit code 137 means SIGKILL, check OOM" is faster than reading the spawn show JSON and inferring it.

**Rejected:**
- *Drop the failure-mode table too.* Loses the only durable content from `__meridian-diagnostics`. Agents need this when state goes weird, and reading it from `meridian doctor --help` would require the doctor help to grow into a troubleshooting guide — wrong altitude for `--help`.
- *Keep the full flag tables, just consolidated into one file.* Same drift, same line count, no benefit.

## D7 — Skip a separate planner; the design is small enough for impl-orchestrator directly

**Decision (recommendation, not forcing):** Recommend that the dev-orchestrator skip spawning a dedicated planner and hand this design straight to impl-orchestrator with a brief phase outline embedded in the handoff.

**Why:** The work decomposes cleanly into three obvious phases:

1. **Expand `--help` text** (`04-cli-help-gaps.md` is the spec). Verification = run each updated `--help`.
2. **Create `__meridian-cli` and the new dev-workflow skill; delete the three old base skills; update consumer profiles; fix the orchestrator-line-29 leak; codify the example-vs-generic policy in anti-patterns docs.** Verification = `meridian mars sync` clean + grep for stale refs returns empty.
3. **README updates and final smoke check.** Verification = manual review.

There are no parallelization questions, no design uncertainties left unresolved, and no risky-but-reversible decisions that benefit from a planner's deeper decomposition. A planner would re-derive the same three phases.

**If the dev-orchestrator disagrees** (e.g., they want a planner to lock the new skill name in phase 1, or to surface help-text edits I missed), spawning one is cheap and harmless. The decision is "default to skipping; spawn one if it adds value." Logged here so future review can second-guess if needed.

## D8 — Don't break the dev-workflow skill at the file level by adding a new resources/ tree

**Decision:** The new dev-workflow `session-mining` skill ships as a single SKILL.md, no resources/. Same for `__meridian-cli`.

**Why:** Both skills are deliberately small. A `resources/` tree would invite the kind of depth that re-introduces the duplication we're cutting. If a future need pushes one of them past ~200 lines, that's the moment to revisit — not now.

**Rejected:** Pre-creating `resources/architecture-overview.md` for `__meridian-cli`. Tempting because the runtime model is genuinely worth a longer doc, but it's a different skill (the eventual `__meridian` that D1 reserves the name for). Don't hide it under `__meridian-cli/resources/`.
