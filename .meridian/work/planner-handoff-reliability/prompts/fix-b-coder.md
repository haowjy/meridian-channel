# Task

Edit the `meridian-spawn` skill to (1) correct a misleading sentence in its Core Loop section and (2) add a new "Wait Before You Finalize" section. The motivation is documented in `.meridian/work/planner-handoff-reliability/requirements.md` (in the meridian-cli repo) — read that if you need background, but the edit itself is fully specified below.

## Target file

`/home/jimyao/gitrepos/prompts/meridian-base/skills/meridian-spawn/SKILL.md`

This is a sibling checkout outside the meridian-cli repo. Edit the file in place there. Commit in that repo (not meridian-cli).

## Edit 1 — revise Core Loop sentence

Find this sentence in the "Core Loop" section (near the top of the file, likely in the second paragraph):

> Spawns block until the spawn completes, then returns the result. The preferred pattern is to spawn these in the background so you get a completion notification later.

Replace with:

> Spawns block until the spawn completes, then return the result. You can run them in the background so your harness delivers a completion notification, but that's a notification convenience — the parent still owns the spawn until it terminates. See "Wait Before You Finalize" below.

Note the grammar fix ("returns" → "return") and the addition of the clarifying clause about ownership.

## Edit 2 — add new H2 section

Add a new H2 section immediately after the "Core Loop" section ends and before the "Spawning" H2 section begins. Exact content:

```markdown
## Wait Before You Finalize

If your turn spawned children, block on their terminal state before
emitting your own report. Use `meridian spawn wait <id>` (or the
multi-spawn form shown in Core Loop). This holds whether the spawn blocked
foreground or launched via background/notification mode — background is a
delivery convenience, not a handoff. The parent owns the spawn until it
terminates.

A report whose body amounts to "waiting for X to complete" is a bug: you
returned control before the work finished, and there is no mechanism to
resume your turn when the children terminate later.

```bash
# Background for parallelism, then block before returning
meridian spawn -a coder -p "phase 2" --desc "phase 2"
meridian spawn -a coder -p "phase 3" --desc "phase 3"
meridian spawn wait p301 p302    # do not emit your report until this returns
```
```

Keep line-wrap consistent with the rest of the file (the skill uses prose-style wrapping, not hard-wrap; match what you see around the edit site).

## Don't

- Don't edit any other skill or any agent profile.
- Don't regenerate `.agents/` in any repo via `meridian mars sync` — propagation is out of scope for this task; the orchestrator will handle that after review.
- Don't change the description frontmatter at the top of the file unless absolutely required by the new section.
- Don't add cross-references to other skills beyond what's already implied.

## Report

When done, report:
1. Confirmation that the file was edited at `/home/jimyao/gitrepos/prompts/meridian-base/skills/meridian-spawn/SKILL.md`.
2. A diff-style summary of the two edits.
3. Any judgment calls (e.g. if the Core Loop sentence was worded slightly differently than expected, show what you actually replaced).
4. Confirmation that you did NOT commit in the meridian-base repo — leave staging and commit to the orchestrator.
