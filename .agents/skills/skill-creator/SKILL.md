---
name: skill-creator
description: >
  Author, edit, review, split, or refactor meridian skill files — the
  SKILL.md files with YAML frontmatter that live under `skills/<name>/` in
  a source submodule and carry reference material loaded into agents on
  demand. Load this skill whenever you're writing a skill from scratch,
  updating a SKILL.md body, adding or reorganizing `resources/`, splitting
  a long skill into variants, or deciding whether something should be a
  skill at all. Phrases that should trigger this skill: "write a skill",
  "create a skill", "add resources to this skill", "the SKILL.md needs
  updating", "split this skill", "this skill is too long", "refactor this
  skill's description".
---

# skill-creator

A guide for writing meridian skills — the reference material agents load
to extend their behavior without spawning a new process. Load this skill
before touching any file under a `meridian-base/`, `meridian-dev-workflow/`,
or similar source submodule's `skills/` directory.

## Hard rule: edit source, never `.agents/`

`.agents/` is generated output from `meridian mars sync`. Anything you edit there
is overwritten the next time someone runs sync, so your edit is invisible
and disappears on the next pull. Edit the source submodule instead —
`meridian-base/skills/<name>/SKILL.md`,
`meridian-dev-workflow/skills/<name>/SKILL.md`, or whichever repo owns
the skill.

Canonical workflow: edit source → commit source → `meridian mars sync` →
`.agents/` regenerates. If you're unsure which submodule owns a skill,
`meridian mars list` shows the source for each installed one.

## What a skill is

A skill is reference material that gets loaded into an agent's context
when it becomes relevant. Skills don't run independently; they shape how
an existing agent behaves. Multiple agents can share the same skill,
which is the whole point — knowledge written once, reused everywhere.

Layout in a source submodule:

```
meridian-base/skills/<name>/
  SKILL.md          (required — frontmatter + body)
  resources/        (optional — loaded on demand from body references)
    something.md
    ...
```

No `scripts/`, no `assets/`, no test infrastructure — meridian skills are
plain reference material. If you need executable behavior, that's an
agent, not a skill.

## Skill vs agent: which are you writing?

A **skill** is knowledge. It doesn't run. It augments an agent that is
already running.

An **agent** is an actor. It's spawned as its own process with its own
context window, makes decisions, calls tools, and produces output.

If it runs independently and produces output, it's an agent. If it's
reference material several agents share, it's a skill.

**Multi-consumer test:** a skill earns its existence by having more than
one consumer. If only one agent would ever load it, the knowledge belongs
in that agent's body — splitting it into a separate skill creates two
files to maintain with no reuse payoff. Extract a skill only when a
second agent needs the same knowledge. For agent authoring, load the
`agent-creator` skill.

## Frontmatter contract

Skill frontmatter is simpler than agent frontmatter. The two core fields:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `name` | string | yes | Skill identifier. Match the directory name. |
| `description` | string | yes | When to use the skill (situations and contexts), not how. This is the primary triggering mechanism — what a model sees when deciding whether to load the body. |

Optional fields (rarely needed):

- `compatibility` — harness or tool requirements, if the skill only works
  in certain environments.

Keep frontmatter minimal. Extra fields tempt consumers to over-configure.

## Progressive disclosure

Skills use a three-level loading system. Each level carries a different
cost and should hold a different kind of content.

### Level 1: description (always in context)

The description is always loaded — it sits in every agent's skill list
until the skill triggers. Because it's cheap and ubiquitous, it should be
short (a sentence or two) and focus on *when* to use the skill, not how.

Two audiences see the description:

1. **Agents with the skill pre-loaded** via the profile's `skills:`
   array. They already have the body, so the description orients rather
   than instructs.
2. **Agents without the skill loaded.** The description is all they see.
   It has to be concrete enough that they decide to load the body at the
   right moment.

Claude has a tendency to undertrigger skills, so descriptions should be
slightly pushy — list the phrases and situations that should fire them,
not just the abstract purpose.

### Level 2: SKILL.md body (loaded when skill triggers)

The body is loaded whenever the skill triggers. Aim for under ~500 lines;
treat that as a soft ceiling, not a rule. The body carries the core loop
and common patterns — the things agents need *every* time they use the
skill. If it grows past the ceiling and you're still adding, push
situational detail into `resources/`.

### Level 3: resources (loaded on demand)

Resources are loaded only when the body explicitly points at them.
Advanced commands, debugging, edge cases, domain variants, long example
collections — anything that matters sometimes but not every invocation.
Reference each resource from the body with guidance on *when* to read it,
so agents know what's available without preloading it.

## Body length discipline

If your SKILL.md is approaching 500 lines, something probably belongs in
a resource file. Common signals:

- A section devotes pages to edge cases the typical invocation never
  hits. Push it to `resources/<topic>.md` and leave a one-line pointer.
- A reference table lists dozens of commands or flags. Push the table to
  `resources/reference.md`.
- Multiple examples illustrate the same point. Pick the best one for the
  body and move the rest to `resources/examples.md`.

The reverse mistake is fragmenting a small skill into many files "for
cleanliness." A skill under 200 lines doesn't need a `resources/`
directory at all.

## When to extract to resources

Extract when the content is:

- **Large** — reference tables, long examples, configuration lists.
- **Situational** — only relevant in specific scenarios (debugging,
  advanced commands, edge cases).
- **Domain-specific** — applies to one variant when the skill covers
  several.

Don't extract when the content is part of the core loop every consumer
needs — that belongs in the body.

## Multi-variant skills: domain organization

When a skill supports multiple domains, frameworks, or providers, organize
resources by variant so agents read only the relevant one:

```
cloud-deploy/
  SKILL.md              (core workflow + variant selection)
  resources/
    aws.md
    gcp.md
    azure.md
```

The body explains the shared loop and points at the right reference:
"if the target is AWS, read `resources/aws.md`; if GCP,
`resources/gcp.md`." Agents load the body plus one variant, not all three.

## Self-containment

Skills shouldn't depend on other skills being loaded first. If your skill
needs a piece of knowledge from another skill, copy what you need rather
than writing "load X skill first." The load order isn't guaranteed and
the dependency chain creates silent breakage when one skill is removed
or renamed.

Self-contained is the pattern — we accept some duplication across skills
(the meridian prompting principles below appear in both `skill-creator`
and `agent-creator`) because it makes each skill usable on its own.

## Meridian prompting principles

These principles shape every skill body you write. They're duplicated in
the `agent-creator` skill because the same craft applies to agent prompts.

### 1. No role identity

Don't tell the reading model "you are a senior engineer" or "you are a
meticulous writer." The PRISM persona study (arxiv:2603.18507) found that
persona prompting activates instruction-following machinery that
interferes with knowledge retrieval and reasoning accuracy; on
discriminative tasks, every persona variant they tested reduced accuracy.
The model doesn't need a costume to follow behavioral instructions —
describe the behavior directly. Skills that open with "as an expert in X
you should..." are leaving accuracy on the table.

### 2. Explain why

Every constraint should include the reasoning behind it. Claude
generalizes from explanations — understanding *why* a rule exists lets
the model apply the principle to novel situations rather than following
the rule literally and missing the point. "Keep bodies under ~500 lines
because longer bodies cost every consumer tokens on every invocation, and
most agents never need the edge cases that would push past that length"
generalizes; a naked "SKILL.md must be under 500 lines" doesn't. Expect
a sentence of reasoning for nearly every constraint.

### 3. Right altitude

Behavioral heuristics with reasoning, not brittle if-then rules and not
vague high-level hand-waving. Too specific and the skill breaks on any
edge case the author didn't anticipate. Too vague and the agent falls
back on defaults that may not match what you wanted. The sweet spot: tell
the reading agent what to do, when, and why, and trust it to apply the
principle. "Push situational detail to resources/ so the body stays
focused on the common case" is at the right altitude.

### 4. Dial back aggressive language

Avoid ALL CAPS, "CRITICAL", "you MUST", "NEVER". Aggressive language was
a reasonable defense against undertriggering on older models; on current
models it pushes toward brittle, literal compliance and overtriggering —
the instruction fires in contexts where it doesn't make sense. As models
keep getting more responsive to system prompts, the threshold for this
keeps dropping. Use ordinary language. "Prefer the imperative form
because it reads more directly" is firmer in practice than "YOU MUST USE
THE IMPERATIVE FORM."

### 5. Don't prescribe sequences

Numbered Step 1 / Step 2 / Step 3 flows constrain the reading agent to a
rigid order that may not fit the task at hand. Anthropic's own guidance
prefers general instructions over prescriptive steps. Describe inputs,
outputs, quality bar, available tools, and when to escalate — then trust
the model to sequence. A skill that says "Step 1: read the frontmatter.
Step 2: parse the body..." is usually reaching for structure it doesn't
need.

### 6. Don't hardcode models

Model rankings and pricing shift month to month. Hardcoding "use opus
for X and gpt-5.4 for Y" means the skill is stale the day a new model
ships. Instead write "fan out across diverse strong models" and point to
`meridian models list` or the `agent-staffing` skill for current guidance.
Match model cost to task value — strong reasoning models for
judgment-heavy work, fast models for bulk work.

### 7. Don't repeat across levels

Each level (description, body, resources) should add new information.
If the description explains something, the body should go deeper or
start from where the description left off, not restate it. If the body
explains something, a resource file shouldn't repeat it. Repetition
wastes tokens on every invocation and creates drift — update one place,
forget the other, and now the agent gets conflicting instructions.

### 8. Agent-vs-skill boundary

Skills are reference material loaded into agents. Agents run
independently and produce output. If only one agent consumes a skill,
that skill's content belongs in the agent body — you've created two
places to maintain with no reuse payoff. If you find yourself writing
behavior, decision-making, or a full workflow into a skill, it probably
wants to be its own agent. Getting this wrong in either direction is
costly; see "Skill vs agent" above when in doubt.

## Description design

The skill description drives triggering. Two rules:

**Describe when, not how.** The body handles the how — commands, syntax,
workflow. The description should answer "what situation makes this skill
relevant?" so agents know when to load the body. A description that
reads like a command reference ("use `meridian spawn -a ...`") is both
wasting the triggering budget on content the agent can't yet use and
leaving the actual triggering question unanswered.

**Be slightly pushy.** Claude undertriggers skills more often than it
overtriggers them. List concrete phrases and situations that should fire
the skill — "trigger on phrases like 'write an agent', 'edit this
profile', 'refactor the @reviewer'" — rather than a polite one-liner.
Pre-loaded skills still need good descriptions because other agents
without them loaded need the same triggering signal.

## Writing style

**Imperative form.** "Push situational detail to resources" reads better
than "You should push situational detail to resources" or "Situational
detail should be pushed to resources." Drop the second person and the
passive voice when you can.

**Explain with examples.** Short before/after pairs beat long prose
explanations. If you find yourself writing four paragraphs about what
not to do, it's usually clearer as a two-example comparison. Reserve
prose for the reasoning — the *why* that example can't carry on its own.

**Principle of lack of surprise.** A skill's contents should not surprise
the user relative to its description. Don't sneak unrelated behavior
into a skill that claims to do one thing.

## Resources

- [`resources/example-skills.md`](resources/example-skills.md) — three
  canonical examples (short utility skill, skill with resources,
  multi-variant skill with domain organization). Read when you're
  starting a new skill and want a shape to crib from.
- [`resources/anti-patterns.md`](resources/anti-patterns.md) — before/
  after pairs for the most common mistakes (HOW in the description,
  reference material in the body, single-consumer skills, level
  duplication, cross-skill dependencies). Read when a skill feels off
  and you're trying to diagnose why.

## Further reference (don't duplicate here)

- `meridian mars list` — installed skills with their source submodules
- `meridian spawn --help` — current spawn flags, including how skills
  are loaded per spawn
- The `agent-creator` skill — the flip side of this craft, for when you
  realize the thing you're trying to write is actually an agent
