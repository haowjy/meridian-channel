# Skill Anti-Patterns

Before/after pairs for the most common mistakes. Each has a short
explanation so you can recognize the pattern in new situations rather
than matching on exact wording.

Policy note: in base-layer docs, dev-workflow agent names are allowed in pure examples but not in generic guidance. If removing the agent name leaves a sentence that is still a valid prescription, rewrite it in layer-zero terms. If removing the name makes the sentence lose instructional value, keep it as an example. This prevents cross-layer leaks without stripping concrete examples that teach concepts clearly.

## 1. Description describes HOW instead of WHEN

**Before:**

```yaml
description: >
  This skill teaches you to run `meridian spawn -a <name> -p "..."` with
  optional `-f` files and `--from` context. It covers the flags, the
  output format, and how to parse the JSON response.
```

**After:**

```yaml
description: >
  Multi-agent coordination via the meridian CLI. Use whenever you need
  to delegate work to another agent, run tasks in parallel, check on
  spawn progress, or inspect spawn outputs. Also use when you want to
  route work to a specific model or provider.
```

Why: the description is a triggering mechanism, not a command reference.
Agents decide whether to load the body based on whether the description
matches their *situation*. "Covers the flags and the output format"
doesn't tell the agent when it should care. The "after" version names
the situations that should fire the skill.

## 2. Body is reference material

**Before:** a 420-line SKILL.md whose middle 250 lines are a table of
every CLI flag with its default, type, and an example.

**After:** a 180-line SKILL.md covering the core loop and common
patterns, with a pointer to `resources/cli-reference.md` for the full
table, annotated with "read this when you need a flag you don't recognize
or when writing a spawn command you haven't seen before."

Why: the full flag table is situational — most invocations use five
flags and no reader needs the other forty on a typical call. Loading all
420 lines into every consumer's context on every invocation is a tax.
Pushing detail to `resources/` with a clear when-to-read pointer keeps
the body focused on the common case without losing the reference
material.

## 3. Single-consumer skill

**Before:** a skill called `reviewer-checklist` that is loaded by exactly
one profile, `reviewer.md`. The skill's body contains the rubric the
@reviewer applies.

**After:** the rubric lives inside `reviewer.md`'s body, and the
standalone skill is deleted.

Why: skills exist to share knowledge across consumers. A skill with one
consumer is two files to maintain instead of one, with no reuse payoff.
The multi-consumer test: only extract a skill when a second agent
genuinely needs the same knowledge. If a third reviewer-like agent shows
up later and needs the same rubric, extract then — the YAGNI cost of
waiting is small, and you'll have a real second consumer to design for.

## 4. Duplication across levels

**Before:**

```markdown
---
name: code-review
description: Structured code review methodology — reading a diff for
  correctness, simplicity, and consistency, and writing findings the
  author can act on.
---

# code-review

This skill provides a structured code review methodology. It helps you
read a diff for correctness, simplicity, and consistency, and write
findings the author can act on.

## Core loop
...
```

**After:**

```markdown
---
name: code-review
description: Structured code review methodology — reading a diff for
  correctness, simplicity, and consistency, and writing findings the
  author can act on.
---

# code-review

Start with the diff, not the full files. The diff already shows exactly
what moved and reading full files wastes context on code that isn't
changing.

## Core loop
...
```

Why: the first body line restates the description verbatim. Every agent
that loads the skill pays tokens to read the same sentence twice. The
"after" version starts where the description left off and adds a
concrete behavioral instruction instead. Each level — description, body,
resources — should add new information, not repeat what came before.

## 5. Cross-skill dependency

**Before:**

```markdown
# my-skill

Before using this skill, make sure the `meridian-spawn` skill is
loaded. Many of the patterns here assume you already know the spawn
commands. If it isn't loaded, stop and load it first.
```

**After:**

```markdown
# my-skill

Spawns in this skill's examples use `meridian spawn -a <name> -p
"task"` with optional `-f` for reference files. If you need the full
spawn surface, see the `meridian-spawn` skill — but the examples here
are self-contained and don't require it to be loaded.
```

Why: skills shouldn't require a specific load order. Load order isn't
guaranteed and the dependency creates silent breakage when the required
skill is renamed or removed. Copy the small bit you need and stay
self-contained. The "after" version names the related skill as a
pointer, not a prerequisite — agents that want more can load it
themselves, but this skill stands on its own.
