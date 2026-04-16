# Task — skill append + orchestrator reiteration + opus version bump

Three sets of edits across two sibling repos. No commits.

## Repo 1: `~/gitrepos/prompts/meridian-base`

### Edit 1 — `skills/meridian-spawn/SKILL.md`: append `run_in_background` example to Parallel Spawns

Current "Parallel Spawns" section (around line 105-113, at HEAD — no pending edits):

```markdown
## Parallel Spawns

Use your harness's native background execution to run multiple spawns concurrently. Each spawn runs in foreground (blocking), but your harness runs them in parallel:

```bash
# Launch these concurrently using your harness's background/parallel execution
meridian spawn -a agent -p "Step A" --desc "Step A"
meridian spawn -a agent -p "Step B" --desc "Step B"
# Each blocks until its spawn completes, then returns results.
```
```

**Append** immediately after the closing ``` of that bash block — before "## Checking Status" begins — the following content:

```markdown

In Claude Code, the mechanism is the Bash tool's `run_in_background: true` parameter — it returns a task ID immediately and delivers a notification when the spawn terminates, so you stay responsive while spawns run:

```bash
Bash("meridian spawn -a agent -p 'Step A' --desc 'Step A'", run_in_background: true)
Bash("meridian spawn -a agent -p 'Step B' --desc 'Step B'", run_in_background: true)
# → both task IDs returned immediately; handle each notification as it arrives.
```

Other harnesses have equivalent mechanisms; use whichever your harness supports.
```

Do **not** modify anything else in the skill. Do **not** add a "Wait Before You Finalize" section. Do **not** change the existing Core Loop paragraph. The file is currently at HEAD and the only change is this append.

## Repo 2: `~/gitrepos/prompts/meridian-dev-workflow`

### Edit 2 — add a reiteration line to four orchestrator profiles

For each of these four files, add the exact same line (verbatim) in the placement described below. Keep the line wording identical across all four profiles — consistency matters for the model picking up the same pattern regardless of which orchestrator is loaded.

**Reiteration line (use this exact text):**

```
Always pass `run_in_background: true` to the Bash tool when invoking `meridian spawn`. The harness returns a task ID immediately and delivers a notification when the spawn terminates, so you stay responsive and can run multiple spawns concurrently.
```

**Placement per file:**

- **`agents/dev-orchestrator.md`** — insert as a new paragraph immediately after the `Bash("meridian spawn -a design-orchestrator ...")` code block (currently around line 33). One blank line above, one blank line below. So the sequence becomes: code block → blank → new line → blank → `Your only action surface is Bash...` paragraph.

- **`agents/impl-orchestrator.md`** — same placement: right after the `Bash("meridian spawn -a coder ...")` code block (currently around line 28).

- **`agents/docs-orchestrator.md`** — same placement: right after the `Bash("meridian spawn -a code-documenter ...")` code block (currently around line 31).

- **`agents/design-orchestrator.md`** — this file has no `Bash(...)` code block. Insert the reiteration line as a new paragraph immediately after the bold "**Always use `meridian spawn` for delegation**" paragraph (currently around line 23). One blank line above, one blank line below.

### Edit 3 — bump model in two profiles to `claude-opus-4-5-20251101`

Meridian supports passthrough of unknown-but-pattern-matching model IDs (`resolve_model` in `src/meridian/lib/catalog/models.py:44` falls back to `pattern_fallback_harness`, which routes `claude-*` to the Claude harness). So the ID does not need to be registered in any catalog — the profile bump alone is sufficient.

Change the YAML frontmatter:

- **`agents/design-orchestrator.md`**: change `model: opus` (line 7) to `model: claude-opus-4-5-20251101`.
- **`agents/impl-orchestrator.md`**: change `model: opus` (line 6) to `model: claude-opus-4-5-20251101`.

Do **not** change the model field in `dev-orchestrator.md` or `docs-orchestrator.md` — they stay as they are.

## Don't

- Don't run `meridian mars sync` anywhere — that's a separate propagation step the orchestrator will handle later.
- Don't commit or stage in either repo.
- Don't touch any other file (other agents, other skills, other profile fields).
- Don't rephrase the reiteration line — use the exact text above for all four profiles.

## Report

1. Confirm the five files edited: `skills/meridian-spawn/SKILL.md` in meridian-base, and the four orchestrator profiles in meridian-dev-workflow.
2. For each file, show the diff (git diff of the target file, scoped).
3. Confirm no commits were made in either repo.
4. Confirm no other files were touched (show `git status` of both repos).
