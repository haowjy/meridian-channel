# Agent Profile Anti-Patterns

Before/after pairs for the most common mistakes. Each one has a short
explanation of why the "before" is worse so you can recognize the pattern
in new situations rather than matching on exact phrasing.

Policy note: in base-layer docs, dev-workflow agent names are allowed in pure examples but not in generic guidance. If removing the agent name leaves a sentence that is still a valid prescription, rewrite it in layer-zero terms. If removing the name makes the sentence lose instructional value, keep it as an example. This prevents cross-layer leaks without stripping concrete examples that teach concepts clearly.

## 1. Role identity instead of behavior

**Before:**

```markdown
You are a senior staff engineer with 15 years of experience reviewing
production code. You have a deep commitment to quality and a sharp eye
for bugs.
```

**After:**

```markdown
Focus on correctness and simplicity. Flag bugs, unnecessary complexity,
and divergence from surrounding conventions. Prefer concrete suggestions
over vague concerns.
```

Why: persona prompting activates instruction-following machinery that
interferes with knowledge retrieval and discriminative reasoning (PRISM,
arxiv:2603.18507). The "senior engineer" costume doesn't make the model
review more carefully — it just adds noise. Describing the actual
behavior is what moves the needle.

## 2. Aggressive language instead of reasoning

**Before:**

```markdown
YOU MUST NEVER EDIT SOURCE FILES. THIS IS CRITICAL. If you edit a source
file you have FAILED the task. ALWAYS use meridian spawn. NEVER use the
Agent tool.
```

**After:**

```markdown
You don't edit source files directly because your value is the continuity
between user intent and the autonomous agents you spawn — dropping into
implementation costs you the altitude needed to notice when an
orchestrator drifts from the user's goal. Delegate through `meridian
spawn`; the built-in Agent tool bypasses meridian's state tracking and
report piping, which would leave the user with no record of what happened.
```

Why: ALL CAPS and "MUST/NEVER" push current models toward brittle literal
compliance and overtriggering — the instruction fires in situations where
it doesn't actually fit. Explaining *why* lets the model generalize the
principle to cases the author didn't anticipate. Use `disallowed-tools`
for hard enforcement instead of yelling.

## 3. Hardcoded model names

**Before:**

```markdown
When you need a review, fan out across opus, gpt-5.4, and codex. Use
gpt-5.3-codex for implementation. Sonnet handles documentation.
```

**After:**

```markdown
When you need a review, fan out across diverse strong models — see
`meridian models list` and the `agent-staffing` skill for current
guidance. Match model strength to task value: judgment-heavy work
(review, architecture) earns stronger models; bulk implementation and
research run well on fast ones.
```

Why: model rankings and pricing shift month to month. The hardcoded
version is stale the day a new model ships, and every agent that quotes
it has to be updated in lockstep. Pointing at a live source (`meridian
models list`) keeps the guidance evergreen. Same principle for the
profile's own `model:` field — pick based on role, expect to revisit.

## 4. Prescriptive numbered sequence

**Before:**

```markdown
## Workflow

Step 1: Read all the files passed with `-f`.
Step 2: Search the codebase for related tests.
Step 3: Write a plan and save it to $MERIDIAN_WORK_DIR/plan.md.
Step 4: Implement the plan.
Step 5: Run the tests.
Step 6: Write a report.
```

**After:**

```markdown
Inputs: task description in the prompt, reference files and prior context
in the surrounding window.

Output: working code with tests passing, plus a short report covering
what changed, what was verified, and any judgment calls.

Quality bar: tests pass, the change is scoped to what was asked, and any
deviation from the caller's stated plan is explained in the report.

Tools: the harness's file and shell tools; `meridian spawn` for
delegating subtasks you can't do alone.

Escalate when the task is ambiguous enough that guessing would waste work
— ask the caller rather than producing something they'll reject.
```

Why: numbered steps constrain the model to a rigid order that often
doesn't fit the task. A simple change doesn't need a plan file; a tricky
one might need review mid-work, not only at the end. Describing inputs,
outputs, quality bar, tools, and escalation lets the model sequence the
work based on the specific situation.

## 5. Caller-specific body

**Before:**

```markdown
The dev-orchestrator spawns you with `--from` containing the session
history and `-f` containing the design docs. Read everything in `--from`
before touching `-f`. Your parent expects a status line on completion.
```

**After:**

```markdown
You receive a task description in the prompt along with reference files
and prior conversation context. Read what's there before acting, and
start with the files the caller explicitly referenced — they're the
most likely to matter.

On completion, write a report covering what you did, what passed, and
any judgment calls or unresolved issues. The report is how any caller,
human or agent, picks up the thread.
```

Why: the receiving model sees whatever context lands in its window and
has no way to distinguish `--from` content from `-f` content from inline
prompt text. Phrases like "read all `--from` context" are meaningless at
the receiving end. Worse, hardcoding a specific parent (@dev-orchestrator)
means the agent only behaves correctly when that parent spawns it — a CI
pipeline or ad-hoc human spawn gets a confused agent. Caller-agnostic
bodies are reusable across workflows.

## 6. Mixing roles in one profile

**Before:** a single `coder-reviewer.md` profile whose body says "first
implement the change, then review it for correctness and flag any issues
you find."

**After:** two profiles — `coder.md` and `reviewer.md` — and an
orchestrator that spawns them in sequence.

Why: asking one model to review its own work is a conflict of interest —
the same context that produced the code biases the judgment of whether
the code is good. It also bloats the system prompt, because the
implementation guidance and the review guidance each dilute the other.
Separate profiles cost almost nothing (they're just files) and produce
genuinely independent reads.
