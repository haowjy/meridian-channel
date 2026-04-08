---
name: agent-creator
description: >
  Author, edit, review, or refactor meridian agent profiles — the markdown
  files with YAML frontmatter that live in an `agents/` directory and define
  reusable spawn configurations (model, system prompt, tools, permissions,
  skills). Load this skill whenever you're writing an agent from scratch,
  tweaking an existing profile, splitting one agent into several, reviewing
  an agent for quality, or deciding whether something should be an agent at
  all. Phrases that should trigger this skill: "write an agent", "create
  a profile", "edit this agent", "add a reviewer agent", "refactor the
  coder agent", "this agent's prompt needs work", "add tools to this
  profile", "tighten up this agent's description".
---

# agent-creator

A guide for writing meridian agent profiles that are reusable, caller-agnostic,
and age well as models and workflows evolve. Load this skill before touching
any file under a `meridian-base/`, `meridian-dev-workflow/`, or similar source
submodule's `agents/` directory.

## Hard rule: edit source, never `.agents/`

`.agents/` is generated output from `meridian mars sync`. Anything you edit there is
overwritten the next time someone runs sync, so the edit is invisible to
everyone else and disappears on the next pull. Edit the source submodule
instead — `meridian-base/agents/<name>.md`,
`meridian-dev-workflow/agents/<name>.md`, or whichever repo owns the profile.

Canonical workflow: edit source → commit source → `meridian mars sync` →
`.agents/` regenerates. If you're unsure which submodule owns an agent,
`meridian mars list` shows the source for each installed profile.

## What an agent profile is

An agent profile is a markdown file with YAML frontmatter under `agents/`
in a source submodule:

```
meridian-base/agents/
  meridian-subagent.md
  meridian-default-orchestrator.md
```

The frontmatter defines a reusable spawn configuration — model, tools,
permissions, skills. The body below the frontmatter is the agent's system
prompt. Together they mean `meridian spawn -a <name>` reproduces the same
agent every time without the caller repeating model flags and preambles.

## Agent vs skill: which are you writing?

An **agent** is an actor. It's spawned as its own process, gets its own
context window, makes decisions, calls tools, and produces output. Agents
are independent.

A **skill** is reference material loaded into whatever agent needs it.
Skills don't run; they shape behavior inside an existing agent.

If it runs independently and produces output, it's an agent. If it's
knowledge that several agents share, it's a skill. Getting this wrong is
costly in both directions: a skill where an agent belongs forces a single
consumer to become a god-object that does everything itself; an agent where
a skill belongs spawns a whole process just to deliver a few hundred lines
of reference.

Test for extracting a skill: does more than one agent need the same
knowledge? If the answer is no, the knowledge belongs in that one agent's
body. Don't split a single agent's guidance across its body and a dedicated
skill just because the body feels long — you'll create two places to
maintain with no reuse benefit. For skill authoring, load the `skill-creator`
skill.

## Frontmatter contract

| Field             | Type     | Required | Purpose |
|-------------------|----------|----------|---------|
| `name`            | string   | yes      | Profile identifier used with `meridian spawn -a <name>`. Match the filename. |
| `description`     | string   | yes      | What the agent does, how to invoke it, what context it needs, where it puts output. Serves the caller deciding whether to spawn. |
| `model`           | string   | no       | Default model. Caller can override with `-m`. Omit to let project config decide. |
| `effort`          | string   | no       | Reasoning effort tier: `low`, `medium`, `high`, `xhigh`. Honored by models that support it. |
| `skills`          | string[] | no       | Skills to load on launch. Only list skills this agent genuinely needs every invocation. |
| `tools`           | string[] | no       | Tool allowlist. Primarily useful for scoping Bash (`Bash(git *)`) and for harnesses like OpenCode/Codex. On Claude, this does not restrict built-in tools. |
| `disallowed-tools`| string[] | no       | Tool denylist. On Claude this genuinely removes tools — use it for hard restrictions like `[Agent]` on orchestrators that must go through `meridian spawn`. |
| `sandbox`         | string   | no       | Permission tier: `read-only`, `workspace-write`, `full-access`, `unrestricted`. Match the tier to the task, not the maximum the agent might ever need. |
| `mcp-tools`       | string[] | no       | MCP tools to expose, e.g. `[fetch, filesystem]`. |
| `approval`        | string   | no       | Approval mode override: `default`, `confirm`, `auto`, `yolo`. |
| `harness`         | string   | no       | Harness override. Usually omit and let model choice derive it. |
| `autocompact`     | bool     | no       | Whether the harness may auto-compact long contexts. |

Don't memorize this — run `meridian spawn --help` and look at existing
profiles in `meridian-base/agents/` and `meridian-dev-workflow/agents/` when
you need a refresher. Profiles evolve faster than docs.

## Agent prompt layout

A well-structured body puts the most important context first so the model
orients quickly after compaction or mid-context recall. These are priorities
ordered by importance, not a template — a short utility agent doesn't need
five sections.

- **Open with what this agent does and why it matters.** Functional
  description, not identity claim. This is what the model sees first if its
  context gets compacted, so it should re-anchor on purpose immediately.
- **Behavioral constraints with reasoning.** What not to do and why. Early
  placement protects these from being lost in long contexts, where primacy
  and recency effects dominate.
- **Core workflow and quality bar.** What inputs arrive, what output is
  expected, what "done" looks like, which tools are available. This is
  usually the bulk of the prompt.
- **Specific guidance per mode.** Escalation paths, completion criteria,
  edge cases. Later placement because these apply situationally.

## Meridian prompting principles

These are the principles that should shape every agent prompt you write.
They're duplicated into the `skill-creator` skill too, because the same
craft applies to skill bodies.

### 1. No role identity

Don't assign personas like "you are a senior engineer" or "you are a careful
reviewer." The PRISM persona study (arxiv:2603.18507) found that persona
prompting activates instruction-following machinery that interferes with
knowledge retrieval and reasoning accuracy; on discriminative tasks
(judgment calls, factual recall, code reasoning), every persona variant
they tested reduced accuracy. The model doesn't need a costume to follow
behavioral instructions — describe the behavior directly. "Focus on
correctness: does the code do what it claims?" does more work than "you are
a careful code reviewer."

### 2. Explain why

Every constraint should include the reasoning behind it. Claude generalizes
from explanations — understanding *why* a rule exists lets the model apply
the principle to novel situations rather than following the rule literally
and missing the point. A naked "never edit source files" is brittle; "you
don't edit source files because your value is the continuity between user
intent and autonomous orchestrators — if you drop into implementation you
lose the altitude to notice drift" generalizes. Expect to write a sentence
of reasoning for nearly every constraint. If you can't explain why, the
constraint probably shouldn't be there.

### 3. Right altitude

Behavioral heuristics with reasoning, not brittle if-then rules and not
vague high-level hand-waving. Too specific and the prompt breaks on any
edge case the author didn't anticipate, which drives constant maintenance.
Too vague and the model falls back on defaults that may not match what you
wanted. The sweet spot: tell the model what to do, when, and why, and
trust it to apply the principle. "Prefer git diff over reading full files
when reviewing a change, because the diff already shows exactly what moved"
lands at the right altitude.

### 4. Dial back aggressive language

Avoid ALL CAPS, "CRITICAL", "you MUST", "NEVER". Aggressive language was a
reasonable defense against undertriggering on older models; on current
models it pushes toward brittle, literal compliance and overtriggering —
the instruction fires in contexts where it doesn't make sense. As models
keep getting more responsive to system prompts, the threshold for this
overtriggering drops. Use ordinary language. "Use `meridian spawn` to
delegate work; the built-in Agent tool bypasses meridian's state tracking"
is firmer in practice than "YOU MUST NEVER USE THE AGENT TOOL."

### 5. Don't prescribe sequences

Numbered Step 1 / Step 2 / Step 3 flows constrain the model to a rigid
order that may not fit the actual task. A simple change doesn't need an
exploration phase. A complex one might need review mid-work, not only at
the end. Anthropic's own guidance prefers general instructions over
prescriptive steps: "think thoroughly" often beats a hand-written plan.
Describe inputs, outputs, quality bar, available tools, and when to
escalate — then trust the model to sequence.

### 6. Don't hardcode models

Model rankings and pricing shift month to month. Hardcoding "fan out
across opus, gpt-5.4, and codex" means the prompt is stale the day a new
model ships. Instead write "fan out across diverse strong models" and
point to `meridian models list` or the `agent-staffing` skill for current
guidance. Match model cost to task value — strong reasoning models for
review and architecture, fast models for bulk implementation and research.
Same principle applies to the profile's own `model:` field: pick based on
the role, not fashion, and expect to revisit it.

### 7. Don't repeat across levels

The description, the body, and any loaded skills each add new information.
If the description already says "reviews code for correctness and
simplicity," the body shouldn't open by saying the same thing — it should
start where the description left off. Repetition wastes tokens on every
invocation and creates maintenance drift: update one place, forget the
other, and now the agent gets conflicting instructions.

### 8. Agent-vs-skill boundary

Agents run independently and produce output. Skills are reference material
loaded into agents. If only one agent consumes a skill, that skill's
content belongs in the agent's body — you've created two places to
maintain with no reuse payoff. If you find yourself putting behavior and
decision-making into a skill, it probably wants to be its own agent.
Getting this wrong in either direction is costly; see the "Agent vs skill"
section above when in doubt.

## Tool restrictions

Two mechanisms, used for different purposes:

- **`tools`** (allowlist) is most useful for scoping Bash — `Bash(git *)`,
  `Bash(rg *)`, etc. — and for OpenCode/Codex where the allowlist is
  enforced at the harness level. On Claude, the allowlist does not
  restrict built-in tools: Read, Glob, Grep, Agent, WebFetch, etc. remain
  available regardless of what you list.
- **`disallowed-tools`** (denylist) is how you enforce real restrictions on
  Claude. The canonical use is `disallowed-tools: [Agent]` on orchestrators
  that must delegate through `meridian spawn` — the built-in Agent tool
  would bypass spawn tracking, report piping, and model routing.

When both are set, both are emitted — the allowlist doesn't suppress the
denylist. Use the denylist for hard no's and the allowlist for scoping
what's available.

## Sandbox tiers

Pick the lowest tier that does the job:

- `read-only` — analysis, review, investigation. The agent can read
  anything but can't modify files or run state-changing commands.
- `workspace-write` — implementation and test work scoped to the repo.
- `full-access` — only when the agent genuinely needs to touch things
  outside the workspace.
- `unrestricted` — last resort.

Matching sandbox to task is how you keep a misbehaving or confused agent
from surprising the user. A @reviewer that only needs `git diff` and
`git log` should not be able to write files.

## Model choice

Match model strength to task value rather than picking a favorite:

- Review, architecture, design, tricky debugging — strong reasoning models
  earn their cost.
- Implementation, documentation, bulk exploration, mechanical refactors —
  fast models are cheaper, ship sooner, and are usually accurate enough.

Don't hardcode names in prose. Set `model:` in the profile so project
config or CLI can override it, and point contributors at
`meridian models list` when they ask which one to use.

## Caller-agnostic bodies

The body shouldn't reference who spawned the agent or how. The agent sees
whatever context landed in its window and has no way to distinguish
`--from` context from `-f` context from inline prompt text. Phrases like
"the @dev-orchestrator spawns you with `--from`" are meaningless to the
receiving model and create a false dependency on a specific caller.

Keeping agents caller-agnostic makes them reusable across workflows — the
same @reviewer can be called from a dev orchestrator, a CI pipeline, or a
human ad-hoc spawn and behave identically.

## Description design

The agent description serves the caller, not the agent itself. Callers may
be humans running `meridian mars list`, orchestrators that have never seen this
profile before, or agents in harnesses without native profile discovery.
Cover:

- **What it does and what it produces** — so the caller can tell whether
  this is the right agent for the task.
- **How to invoke it** — include the `meridian spawn -a <name>` shape so
  callers in any harness can copy the pattern.
- **What context it needs** — e.g. "pass conversation context with
  `--from` and relevant files with `-f`, or mention specific files in the
  prompt so the agent can explore on its own." This is one of the few
  places where naming invocation mechanics is appropriate, because the
  caller is the audience.
- **Where it puts output** — e.g. `$MERIDIAN_WORK_DIR/design/`, so
  orchestrators don't have to read agent code or wait for completion to
  find artifacts.

The body, by contrast, should describe behaviors directly and stay silent
on invocation mechanics.

## One role per profile

A profile that mixes review and implementation creates a conflict of
interest — the same model is both writing and judging its own work — and
bloats the system prompt, diluting both sets of instructions. When you're
tempted to stuff a second role into a profile, write a second profile.

## Resources

- [`resources/example-profiles.md`](resources/example-profiles.md) — three
  canonical examples (minimal utility agent, @reviewer, orchestrator). Read
  when you're starting a new profile and want a shape to crib from.
- [`resources/anti-patterns.md`](resources/anti-patterns.md) — before/after
  pairs for the most common mistakes (role identity, aggressive language,
  hardcoded models, prescriptive sequences, caller-specific bodies). Read
  when a profile feels off and you're trying to diagnose why.

## Further reference (don't duplicate here)

- `meridian mars list` — installed agents and skills with their source submodules
- `meridian spawn --help` — current spawn flags and shapes
- `meridian models list` — available models with strengths and cost tiers
- The `agent-staffing` skill — team composition guidance for design and
  implementation phases
