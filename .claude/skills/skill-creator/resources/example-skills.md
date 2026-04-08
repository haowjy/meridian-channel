# Example Skills

Three canonical shapes to crib from when writing a new skill. Each shows
the layout, the frontmatter, and enough of the body to see the structure,
with notes on the choices made.

## 1. Short utility skill (no resources)

A small skill whose entire content fits in the body. No `resources/`
directory, no `scripts/`, just a SKILL.md. Most meridian skills start
here and only grow a resources directory if they need one.

Layout:

```
meridian-base/skills/meridian-spawn-checkin/
  SKILL.md
```

```markdown
---
name: meridian-spawn-checkin
description: >
  Check in on in-flight meridian spawns — listing active ones, reading
  their reports, and deciding whether to wait, cancel, or move on. Use
  whenever you've spawned work and are about to take another action that
  depends on the outcome. Trigger on phrases like "is the spawn done",
  "check on the reviewer", "what did p107 say".
---

# meridian-spawn-checkin

When you have spawns running and need to decide what to do next, start
with the work dashboard:

```bash
meridian work
```

It shows active work items with their attached spawns and current
status. If a spawn is still running and you need its result before you
can proceed, block on it:

```bash
meridian spawn wait <spawn_id>
```

Otherwise move on and let the notification pick up the result. Polling
a running spawn in a loop is a waste — meridian sends a notification
when each one finishes.

If a spawn shows `failed`, read its report:

```bash
meridian spawn show <spawn_id>
```

The report usually contains the error or the agent's last output. If
the error is environmental (network, credentials), retry. If it's the
agent hitting a dead end, read the report carefully before spawning a
replacement — the replacement will hit the same dead end unless the
caller briefs it differently.
```

Notes:

- Whole skill fits in a body — no `resources/`.
- Description lists concrete trigger phrases, because Claude
  undertriggers polite descriptions.
- Imperative form throughout ("start with the dashboard" not "you
  should start with the dashboard").
- Explains *why* (polling is wasteful; retry only for environmental
  failures), not just what.

## 2. Skill with resources

A skill whose body carries the common case and pushes less-common
material into `resources/`. This is the shape most skills grow into as
they mature.

Layout:

```
meridian-base/skills/code-review/
  SKILL.md
  resources/
    severity-rubric.md
    large-diffs.md
```

Body excerpt:

```markdown
---
name: code-review
description: >
  Structured code review methodology — reading a diff for correctness,
  simplicity, and consistency, and writing findings the author can act
  on. Use whenever you're asked to review a change, assess a PR,
  evaluate a patch, or triage an agent's implementation. Trigger on
  phrases like "review this change", "look over the diff", "is this
  patch ok".
---

# code-review

Start with the diff, not the full files. The diff already shows exactly
what moved and reading full files wastes context on code that isn't
changing.

## Core loop

Read the diff once end to end before writing any findings — first-pass
reactions often shift once you see how the pieces fit together. Then do
a second pass and write findings with:

- File and line reference
- Severity tag (blocking, important, nit) so the author can triage
- A concrete suggestion where possible — "rename `x` to `userId` because
  the surrounding code uses that term" beats "naming could be clearer"

For the severity rubric — when to tag blocking vs important vs nit, and
how to handle edge cases like style preferences — see
[`resources/severity-rubric.md`](resources/severity-rubric.md). Read it
the first time you review on a new codebase, or when you're unsure
whether a finding is serious enough to block.

## Large diffs

Reviews over ~500 lines of diff need a different approach — see
[`resources/large-diffs.md`](resources/large-diffs.md) for the
chunking strategy. Read it when the diff is big enough that you'd lose
track trying to hold it in your head.
```

Notes:

- Body covers the common case (normal-sized diffs, standard loop).
- `resources/severity-rubric.md` holds the full rubric because most
  reviews don't need the edge cases, and new @reviewers can read it once
  and internalize it.
- `resources/large-diffs.md` holds a different strategy for a
  situational case. Gated by a clear trigger ("diff over ~500 lines")
  so the agent knows when to load it.
- Both resource references include *when to read* guidance, not just
  "see resources/X.md".

## 3. Multi-variant skill with domain organization

A skill that covers several variants (frameworks, providers, harnesses).
The body carries the shared workflow and variant selection; each variant
lives in its own resource file so agents load only the one they need.

Layout:

```
meridian-base/skills/harness-debugging/
  SKILL.md
  resources/
    claude.md
    codex.md
    opencode.md
```

Body excerpt:

```markdown
---
name: harness-debugging
description: >
  Diagnose and fix harness-level problems when a meridian spawn
  misbehaves — the agent didn't get the right tools, a permission prompt
  hung forever, the wrong model was used, output wasn't captured. Use
  when a spawn fails with an error that points at the harness rather
  than the task. Trigger on phrases like "the spawn hung", "the agent
  can't run tools", "approval prompt isn't appearing", "model wasn't
  honored".
---

# harness-debugging

Harness bugs look like task failures but the root cause is in the
adapter between meridian and the runtime (Claude, Codex, OpenCode).
Symptoms that point here rather than at the agent:

- Agent starts and then hangs with no output
- Tools that should be available are missing
- Approval prompts don't appear or auto-deny
- Model flag was honored by meridian but ignored by the runtime

## Shared first steps

Read the spawn report and the raw harness log:

```bash
meridian spawn show <spawn_id>
```

The report usually quotes the harness stderr, which is where adapter
errors surface. If the report is empty but the spawn shows `failed`,
the adapter crashed before writing — look at meridian's own stderr
from the parent session.

## Variant-specific debugging

Harness behavior diverges past this point. Read only the variant
relevant to the failing spawn:

- Claude: [`resources/claude.md`](resources/claude.md)
- Codex: [`resources/codex.md`](resources/codex.md)
- OpenCode: [`resources/opencode.md`](resources/opencode.md)

You can tell which harness ran the spawn from `meridian spawn show` —
look for the `harness` field.
```

Notes:

- Body holds the shared diagnostic loop and the selection logic —
  everything that applies regardless of harness.
- Each variant gets its own resource file. Agents load the body plus
  one variant, not all three.
- Selection is explicit: the body tells the agent how to pick, and the
  signal for picking (`harness` field in spawn show) is named so the
  agent doesn't have to guess.
- No cross-references between variant files — each is self-contained,
  so an agent reading `claude.md` doesn't need `codex.md` loaded too.
