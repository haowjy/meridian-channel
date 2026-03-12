# Design: Optional Dev Workflow Skills + Agent Profiles

## Summary

Encode a reusable, language/framework-agnostic software development workflow as optional skills and agent profiles in the `meridian-agents` repo. The workflow covers design → adversarial review → implementation planning → phased implementation → tracking, with GitHub issue tracking replacing local markdown logs.

Reference implementation: `meridian-collab/_docs/plans/ws-transport-v2/` — a manually orchestrated Go/WebSocket refactor that this design generalizes into reusable skills.

## 1. Skill Composition Model

Skills are always attached to agent profiles via the profile's `skills` field — never injected ad-hoc. If an orchestrator wants a subagent to use a skill, it picks an agent profile that has that skill. If the orchestrator itself needs a skill, the user configures their custom primary agent profile to include it.

**Two levels of primary orchestrator:**

- `__meridian-primary` — core, auto-synced. Minimal: `__meridian-orchestrate` + `__meridian-spawn-agent`. Just enough to plan/delegate/evaluate.
- `primary` — optional, opinionated. Includes core skills (`__meridian-orchestrate`, `__meridian-spawn-agent`) plus `dev-workflow`. The full software development lifecycle orchestrator, ready to use. Users on GitHub repos can also attach `issue-tracking` for GH issue integration.

**How users get started:**

```bash
meridian sync install meridian-agents          # sync everything
meridian config set default-agent primary      # use the opinionated orchestrator
```

Or compose their own:

```bash
cp .agents/agents/primary.md .agents/agents/my-primary.md
# edit skills list, model, etc.
meridian config set default-agent my-primary
```

The optional agent profiles (coder, reviewer-solid, etc.) come pre-configured with the right skills attached. The `primary` profile comes pre-configured with the dev workflow.

## 2. Skill Catalog

Four optional skills. Each lives in `meridian-agents/skills/` and is attached to agent profiles that need it:

### `dev-workflow` (for primary orchestrator)

The master playbook. Teaches the orchestrator the full development lifecycle and how to staff each phase. Users attach this to their custom primary agent profile.

**What it teaches:**

1. **Design phase** — interactive discussion with the user, structured design doc in `$MERIDIAN_WORK_DIR/`, set work status to `designing`
2. **Review phase** — fan out adversarial reviewers with different lenses, synthesize findings, resolve conflicts, set status to `reviewing`
3. **Planning phase** — create implementation plan with phases, dependency graph, agent headcount per phase, set status to `planning`
4. **Implementation phase** — execute phases with the review loop, set status to `implementing`
5. **Completion** — final verification, mark `done`

**Lifecycle statuses** (standardized vocabulary for `meridian work update --status`):

| Status | Meaning |
|--------|---------|
| `designing` | Interactive design discussion, creating design docs |
| `reviewing` | Adversarial review of design or implementation |
| `planning` | Creating implementation plan + agent headcount |
| `implementing` | Executing implementation phases |
| `done` | Complete |

These show up in `meridian work list` so any agent can see what phase every work item is in.

**Execution workflow per implementation phase:**

```
1. Orchestrator composes implementation prompt
   - References: design docs (-f), existing code (-f), previous findings
   - Clear scope boundaries: one phase, specific files
   |
   v
2. meridian spawn -a coder -m codex -p "Phase N: ..." -f [context files]
   - Wait for completion
   - Read report
   |
   v
3. Orchestrator evaluates implementation report
   - Check: did it follow the design? any deviations?
   - Create GH issues for unexpected findings
   |
   v
4. Fan out 2-3 reviewers (parallel, different lenses)
   meridian spawn -a reviewer-solid -p "Review Phase N" -f [files]
   meridian spawn -a reviewer-concurrency -p "Review Phase N" -f [files]
   meridian spawn wait <id1> <id2>
   |
   v
5. Orchestrator synthesizes review findings
   - CRITICAL → must fix before approve
   - HIGH → orchestrator decides (fix or defer as GH issue)
   - MEDIUM/LOW → create GH issue, move on
   |
   v
6. If issues: spawn targeted fix + re-review (max 3 cycles)
   If clean: commit, update plan status, move to next phase
```

**Phase gate rules:**
- Tests must pass before moving to next phase
- Commit after each phase that passes
- Don't accumulate changes across phases

**Cross-workspace coordination:**
- Before starting design, check `meridian work list` for active work items and their statuses
- Read other work items' design docs if they touch overlapping areas
- If parallel work touches the same area, note it in a GH issue and design around it
- Prefer separate worktrees for parallel work items

**Design phase artifacts** (created in `$MERIDIAN_WORK_DIR/`):

| Artifact | Purpose |
|----------|---------|
| `overview.md` | Design overview — problem, approach, architecture |
| `decision-log.md` | Append-only decisions (immutable entries, D-1, D-2, ...) |
| `implementation-log.md` | Append-only log during implementation: bugs, weird findings, backlog items |
| `plan/` | Implementation plan with per-phase step files |

**Local tracking is the default.** All tracking artifacts live in `$MERIDIAN_WORK_DIR/` as markdown files. The `dev-workflow` skill works standalone with no external dependencies.

If `issue-tracking` is also attached to the profile, it upgrades tracking: bugs and backlog items additionally get created as GH issues. But the local files remain the source of truth — GH issues are a visibility enhancement, not a replacement.

### `reviewing` (reviewer subagent skill)

Teaches any reviewer agent how to do structured code review. Loaded by all `reviewer-*` agent profiles.

**What it teaches:**
- Structured findings format: ID, severity (CRITICAL/HIGH/MEDIUM/LOW), description, evidence (file:line), suggested fix
- Review lens focus — the agent profile sets the lens (e.g., "concurrency"), the skill teaches the process
- Adversarial mindset — look for what's wrong, not what's right. Challenge assumptions. Find the non-obvious.
- Consolidated output — deduplicate findings, group by severity, clear action items
- Evidence-based — every finding must reference specific code (file, line, function)

**Findings format:**

```markdown
### F-{N}: {Title} [{SEVERITY}]
**File:** `path/to/file.go:123`
**Issue:** What's wrong and why it matters
**Evidence:** The specific code pattern or behavior observed
**Fix:** Concrete suggestion (or "needs investigation")
```

**Review lens vocabulary** (set by agent profile, skill interprets):
- `solid` — SOLID principles, code style, project consistency, correctness
- `concurrency` — races, deadlocks, lock ordering, goroutine/thread leaks
- `security` — auth bypass, input validation, rate limiting, resource exhaustion
- `planning` — architecture alignment, design doc drift, does this phase set up the next correctly?
- `general` — broad review, no specific focus (default)

### `issue-tracking` (enhancement, any agent)

Optional enhancement that teaches agents to mirror tracking artifacts to GitHub issues via the `gh` CLI. This is a visibility layer on top of `dev-workflow`'s local tracking — not a replacement.

**Graceful degradation:** The skill teaches agents to check `gh auth status` first. If `gh` is unavailable, not authenticated, or the repo isn't on GitHub, skip issue creation silently. The local tracking files in `$MERIDIAN_WORK_DIR/` are always the source of truth.

**What it teaches:**
- When to create a GH issue (in addition to logging locally)
- Label taxonomy and how to apply it
- Issue body format (structured, with context)
- Linking issues to work items via labels

**When to create a GH issue:**
- Bug found during implementation that can't be fixed now (would distract from current phase)
- Unexpected/surprising behavior that implementers should know about
- Backlog item discovered — something that needs doing but isn't in scope
- Design decision that was deferred or needs investigation
- Review finding that was deferred (HIGH/MEDIUM severity, not blocking)

**When NOT to create a GH issue:**
- CRITICAL review findings — fix them now, in the current phase
- Things that are in scope and being fixed in this phase
- Design decisions that were made and recorded in `decision-log.md`

**Label taxonomy:**

| Label | Purpose | Color |
|-------|---------|-------|
| `bug` | Bug found during implementation | red |
| `unexpected` | Surprising behavior, "what's weird" | orange |
| `backlog` | Work needed but out of current scope | blue |
| `deferred` | Explicitly deferred from current work | yellow |
| `review-finding` | From code review, not blocking | purple |
| `decision-needed` | Needs a decision before it can be worked on | pink |
| `work:<slug>` | Links to meridian work item | grey |

**Issue body template:**

```markdown
## Context
Found during: [work item name], [phase]
Found by: [agent role] ([spawn ID])

## Description
[What was found]

## Evidence
[File paths, code snippets, reproduction steps]

## Suggested Action
[What should be done, or "needs investigation"]

---
*Created by meridian agent during `work:<slug>` implementation*
```

**Commands the skill teaches:**

```bash
# Create issue with labels
gh issue create --title "Bug: ..." --body "..." --label "bug,work:auth-refactor"

# List issues for a work item
gh issue list --label "work:auth-refactor"

# List all deferred items across work items
gh issue list --label "deferred"

# Close a decision issue when decided
gh issue close <number> --comment "Decided: ..."
```

### `documenting` (documenter subagent skill)

Teaches the documenter agent how to keep docs in sync with code changes.

**What it teaches:**
- Two-pass pattern: cheap discovery scan (haiku), then quality writing (opus)
- What to look for: design doc drift, stale API contracts, missing architecture diagrams
- When to update vs. when to flag — small fixes inline, big changes need orchestrator approval
- Output format: list of files changed with before/after summary

**Two-pass usage:**

```bash
# Discovery (cheap model)
meridian spawn -a documenter -m haiku -p "Find all docs affected by Phase N changes" -f [changed files]

# Writing (quality model)
meridian spawn -a documenter -m opus -p "Update these docs: ..." -f [affected docs]
```

## 3. Agent Profiles

All defined in `meridian-agents/agents/`. Each is a `.md` file with YAML frontmatter that specifies model, skills, sandbox, and a system prompt for the role. Skills are baked into the profile — the orchestrator just picks the right profile with `-a`.

### Builders

| Profile | Default Model | Skills | Sandbox | Purpose |
|---------|--------------|--------|---------|---------|
| `coder` | codex | `issue-tracking` | workspace-write | Write production code following design docs |
| `researcher` | codex | — | read-only | Read-only codebase exploration + web search |

### Reviewers

Each reviewer variant loads the `reviewing` skill but has a different system prompt that sets the lens. This prevents the "review everything shallowly" problem — each reviewer goes deep on one dimension.

| Profile | Default Model | Skills | Sandbox | Lens |
|---------|--------------|--------|---------|------|
| `reviewer` | gpt | `reviewing` | read-only | General review, no specific focus |
| `reviewer-solid` | gpt | `reviewing` | read-only | SOLID principles, code style, correctness |
| `reviewer-concurrency` | gpt | `reviewing` | read-only | Races, deadlocks, lock ordering, leaks |
| `reviewer-security` | gpt | `reviewing` | read-only | Auth bypass, input validation, resource exhaustion |
| `reviewer-planning` | opus | `reviewing` | read-only | Architecture alignment, design doc drift |

### Testers

| Profile | Default Model | Skills | Sandbox | Purpose |
|---------|--------------|--------|---------|---------|
| `unit-tester` | gpt | `issue-tracking` | workspace-write | Write focused tests, run them. Most are disposable — only keep regression guards. |
| `smoke-tester` | sonnet | `issue-tracking` | workspace-write | QA from outside — curl, scripts, race probes. Tests go in scratch dir (gitignored). |

### Support

| Profile | Default Model | Skills | Sandbox | Purpose |
|---------|--------------|--------|---------|---------|
| `documenter` | opus | `documenting` | workspace-write | Keep docs in sync. Two-pass: discovery (haiku) then writing (opus). |

### Primary Orchestrator (optional, ships in repo)

| Profile | Default Model | Skills | Sandbox | Purpose |
|---------|--------------|--------|---------|---------|
| `primary` | claude-opus-4-6 | `__meridian-orchestrate`, `__meridian-spawn-agent`, `dev-workflow` | unrestricted | Full dev lifecycle orchestrator. Superset of `__meridian-primary` with structured dev workflow. Add `issue-tracking` for GH integration. |

This is the ready-to-use orchestrator. Users install it with `meridian config set default-agent primary`. To customize further, copy to `my-primary.md` and edit.

## 3. What Changes in Core vs. What's Purely Skills

### Nothing changes in meridian core

The work item system already supports:
- Free-form status (`meridian work update --status designing`)
- Work dirs with arbitrary files (`$MERIDIAN_WORK_DIR/`)
- Spawn association via `--work` flag
- `meridian work list` showing status

The `dev-workflow` skill just standardizes how agents use these existing primitives.

### Skills own the workflow policy

- What phases exist and their order
- What agents to spawn per phase
- How to staff reviews (which lenses, how many)
- When to create GH issues vs. fix inline
- Phase gate rules
- Cross-workspace coordination norms

This follows the meridian philosophy: "core owns primitives, skills own workflow policy."

## 4. Cross-Workspace Coordination

Visibility-based, no locking or claims. The `dev-workflow` skill teaches agents:

1. Before starting design work, run `meridian work list` to see what's active
2. Read design docs of overlapping work items (check `$MERIDIAN_WORK_DIR/overview.md`)
3. If your work touches the same area as another active work item:
   - Read their design doc and design around it
   - Log the overlap in `implementation-log.md` (category=coordination)
   - If `issue-tracking` is available, also create a GH issue: `--label "backlog,work:<your-slug>"`
   - Prefer a separate worktree so you don't conflict with their files
4. Agents in different workspaces can read each other's design docs but should not modify them

### What `meridian work list` shows

```
$ meridian work list
WORK               STATUS          SPAWNS
auth-refactor       designing       0
ws-transport-v2     implementing    3 (2 running, 1 succeeded)
test-cleanup        reviewing       1 (1 running)
```

An agent seeing this knows:
- `auth-refactor` is still being designed — read the design doc if your work touches auth
- `ws-transport-v2` is mid-implementation — don't touch WS code without coordination
- `test-cleanup` is being reviewed — test changes might be incoming

## 5. Tracking: Local First, GitHub Optional

### Default (dev-workflow only, no external dependencies)

All tracking lives in `$MERIDIAN_WORK_DIR/` as markdown files:

| Artifact | Format | Purpose |
|----------|--------|---------|
| `decision-log.md` | Append-only, immutable entries (D-1, D-2, ...) | Design decisions with rationale and alternatives |
| `implementation-log.md` | Append-only entries (IL-1, IL-2, ...) with category tags | Bugs, weird findings, backlog items, deferred review findings |
| `plan/` | Per-phase step files | Implementation phases with scope, files, dependencies, verification |

This is the same pattern as the ws-transport-v2 reference — it works, it's simple, and it has no dependencies.

### Enhanced (dev-workflow + issue-tracking)

When `issue-tracking` is also attached, agents mirror actionable items to GH issues:

| Local artifact entry | Also created as | GH Labels |
|---------------------|-----------------|-----------|
| IL entry: category=bug | GH issue | `bug`, `work:<slug>` |
| IL entry: category=unexpected | GH issue | `unexpected`, `work:<slug>` |
| IL entry: category=backlog | GH issue | `backlog`, `work:<slug>` |
| IL entry: category=deferred | GH issue | `review-finding`, `deferred`, `work:<slug>` |
| Decision log entries | NOT mirrored | — |

The local files remain the source of truth. GH issues provide searchability, linkability, and visibility across the team. If `gh` is unavailable, the workflow continues with local tracking only.

## 6. Future: Automation & Cron

The skills are designed so they can be triggered programmatically:

```bash
# Automated simple fix
meridian spawn -a coder -m codex -p "Fix issue #42: typo in error message" --work quick-fixes

# Periodic backlog groomer (requires issue-tracking skill on the agent)
meridian spawn -a coder -m sonnet -p "Review open issues labeled 'backlog'. Close stale ones, re-label misclassified ones."

# Cron: weekly triage
0 9 * * 1 meridian spawn -a coder -m haiku -p "Triage unlabeled issues and suggest categorization"
```

No special cron integration needed — `meridian spawn` is already a CLI command that can be called from cron, CI, or scripts.

## 7. Repo Structure

```
meridian-agents/
  agents/
    # Core (auto-synced, __ prefix)
    __meridian-primary.md
    __meridian-subagent.md
    # Optional (user installs with meridian sync)
    primary.md
    coder.md
    researcher.md
    reviewer.md
    reviewer-solid.md
    reviewer-concurrency.md
    reviewer-security.md
    reviewer-planning.md
    unit-tester.md
    smoke-tester.md
    documenter.md
  skills/
    # Core (auto-synced, __ prefix)
    __meridian-orchestrate/
      SKILL.md
    __meridian-spawn-agent/
      SKILL.md
      resources/
        advanced-commands.md
        debugging.md
    # Optional
    dev-workflow/
      SKILL.md
    reviewing/
      SKILL.md
    issue-tracking/
      SKILL.md
    documenting/
      SKILL.md
  README.md
  LICENSE
```

### Installing optional skills

```bash
# Install everything
meridian sync install meridian-agents

# Install specific skills + agents
meridian sync install meridian-agents --skills dev-workflow,reviewing,issue-tracking --agents coder,reviewer-solid,reviewer-concurrency

# Install just the reviewer agents
meridian sync install meridian-agents --agents reviewer,reviewer-solid,reviewer-concurrency,reviewer-security,reviewer-planning
```

## 8. README for `meridian-agents` Repo

The README should be a quick-start guide. Not exhaustive docs — just enough to get running.

```markdown
# meridian-agents

Official agent profiles and skills for [meridian](https://github.com/haowjy/meridian-channel).

## Quick Start

# Install all agents and skills
meridian sync install meridian-agents

# Use the full dev workflow orchestrator
meridian config set default-agent primary

That's it. You now have access to specialized agents for coding, reviewing,
testing, and documentation — plus a structured dev workflow with GitHub issue tracking.

## What's Included

### Core (auto-synced on every `meridian` launch)

These are required for meridian to function. You don't need to install them manually.

| Name | Type | Purpose |
|------|------|---------|
| `__meridian-primary` | agent | Minimal primary orchestrator |
| `__meridian-subagent` | agent | Default subagent |
| `__meridian-orchestrate` | skill | Plan/delegate/evaluate loop |
| `__meridian-spawn-agent` | skill | Spawn CLI coordination |

### Optional

Install with `meridian sync install meridian-agents`.

**Primary orchestrator:**

| Name | Type | Purpose |
|------|------|---------|
| `primary` | agent | Full dev lifecycle orchestrator (design → review → plan → implement → track) |

**Builder agents:**

| Name | Type | Purpose |
|------|------|---------|
| `coder` | agent | Write production code |
| `researcher` | agent | Read-only codebase exploration |

**Reviewer agents:**

| Name | Type | Purpose |
|------|------|---------|
| `reviewer` | agent | General code review |
| `reviewer-solid` | agent | SOLID principles, correctness |
| `reviewer-concurrency` | agent | Races, deadlocks, leaks |
| `reviewer-security` | agent | Auth, input validation, resource exhaustion |
| `reviewer-planning` | agent | Architecture alignment, design doc drift |

**Tester agents:**

| Name | Type | Purpose |
|------|------|---------|
| `unit-tester` | agent | Write and run focused tests |
| `smoke-tester` | agent | QA from outside — scripts, curl, probes |

**Support agents:**

| Name | Type | Purpose |
|------|------|---------|
| `documenter` | agent | Keep docs in sync with code changes |

**Skills:**

| Name | Purpose |
|------|---------|
| `dev-workflow` | Structured dev lifecycle for the primary orchestrator |
| `reviewing` | Structured code review with severity levels |
| `issue-tracking` | GitHub issue creation for bugs, backlog, findings |
| `documenting` | Two-pass doc maintenance (discovery then writing) |

## Usage

### Spawn a coder
meridian spawn -a coder -p "Implement the auth middleware" -f design.md

### Fan out reviewers
meridian spawn -a reviewer-solid -p "Review auth middleware" -f src/auth.py
meridian spawn -a reviewer-security -p "Review auth middleware" -f src/auth.py

### Run tests
meridian spawn -a unit-tester -p "Write tests for auth middleware" -f src/auth.py
meridian spawn -a smoke-tester -p "Test login flow end-to-end"

## Selective Install

# Just the reviewer agents
meridian sync install meridian-agents --agents reviewer,reviewer-solid,reviewer-security

# Just the issue-tracking skill
meridian sync install meridian-agents --skills issue-tracking

## Customizing

Core agents (prefixed with `__`) are managed by meridian and will be overwritten on sync.
Optional agents can be customized freely.

To create your own primary orchestrator:

cp .agents/agents/primary.md .agents/agents/my-primary.md
# edit my-primary.md — change model, add/remove skills
meridian config set default-agent my-primary
```

## 9. Implementation Sequence

1. **Write the skill files** — `dev-workflow/SKILL.md`, `reviewing/SKILL.md`, `issue-tracking/SKILL.md`, `documenting/SKILL.md`
2. **Write the agent profiles** — all the `.md` files listed above
3. **Add to `meridian-agents` repo** — commit to `haowjy/meridian-agents`
4. **Test** — use `meridian sync install meridian-agents` to sync, then run a real work item using the workflow
5. **Iterate** — refine skills based on actual usage

No meridian core changes required for the skills and profiles themselves. However, this design depends on the broader `meridian-agents` infrastructure landing first (auto-sync, well-known sources, `meridian config set`, selective `--skills/--agents` sync). See `design.md` for that prerequisite work.
