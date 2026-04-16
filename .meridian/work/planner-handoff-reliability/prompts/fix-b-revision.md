# Task — revise the "Wait Before You Finalize" section

The first pass at `~/gitrepos/prompts/meridian-base/skills/meridian-spawn/SKILL.md` landed cleanly but a reviewer flagged two Medium correctness issues in the new section. Fix both now.

## Issues to address

### 1. Bash example is misleading

The current example:

```bash
# Background for parallelism, then block before returning
meridian spawn -a coder -p "phase 2" --desc "phase 2"
meridian spawn -a coder -p "phase 3" --desc "phase 3"
meridian spawn wait p301 p302    # do not emit your report until this returns
```

Problems:
- No `--background` flag, no shell backgrounding — these commands run serially.
- `p301 p302` are placeholder IDs the reader never captured.
- The section is specifically teaching the failure mode from a real incident; the example teaching the wrong mechanics undermines the point.

**Fix: remove the bash example entirely.** The principle being taught is *when* to wait, not *how* to spawn in parallel. The existing "Core Loop" section (just above) and the later "Parallel Spawns" section already show accurate patterns for multi-spawn waiting. A duplicated example here would just drift from those.

### 2. "No mechanism to resume your turn" overstates

Current text:
> "...there is no mechanism to resume your turn when the children terminate later."

This reads as if Meridian has no reattachment path at all, which is false — `meridian spawn wait <id>` reattaches to an in-flight spawn and `meridian spawn --continue SPAWN_ID` starts a follow-up spawn in the same harness session. The accurate narrow claim is about the *parent turn specifically*: once the parent finalizes its report, that turn is closed and can't consume child results.

**Fix: rewrite the sentence to be narrow and accurate.** Suggested wording (tune slightly if you can make it cleaner):

> "A report whose body amounts to 'waiting for X to complete' is a bug: you returned control before the work finished, and the parent turn cannot be reopened once finalized to consume the children's results."

## Target file

`/home/jimyao/gitrepos/prompts/meridian-base/skills/meridian-spawn/SKILL.md`

## What the section should look like after this revision

The "Wait Before You Finalize" H2 section should end up as:

```markdown
## Wait Before You Finalize

If your turn spawned children, block on their terminal state before emitting
your own report. Use `meridian spawn wait <id>` (or the multi-spawn form shown
in Core Loop). This holds whether the spawn blocked foreground or launched via
harness-level background mode — background is a delivery convenience, not a
handoff. The parent owns the spawn until it terminates.

A report whose body amounts to "waiting for X to complete" is a bug: you
returned control before the work finished, and the parent turn cannot be
reopened once finalized to consume the children's results.
```

Two deltas from the current file state:
- Delete the fenced bash block entirely.
- Replace the final sentence of the second paragraph as shown.

Match the existing skill's line wrapping style — the file uses prose-style wrapping (no hard-wrap) based on what's already there.

Don't touch the "Core Loop" edit (sentence revision) from the first pass — it's correct.

## Don't

- Don't edit any other skill, profile, or file.
- Don't commit or stage — leave that to the orchestrator.

## Report

1. Confirm both deltas landed.
2. Show the final text of the section after edits.
3. Note anything else you noticed during the edit (e.g. if the surrounding prose needs a connecting phrase after the bash block is removed).
