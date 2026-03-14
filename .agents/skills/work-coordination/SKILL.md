---
name: work-coordination
description: Meridian work lifecycle and artifact placement for orchestrators. Use this whenever you need to create, switch, update, or complete a work item, or decide where work-scoped notes versus broader shared docs belong.
---

# Work Coordination

This skill owns Meridian work-management policy for orchestrators.

Use it to answer:

- when to run `meridian work start`, `switch`, `update`, `done`, or `clear`
- what counts as the authoritative work record
- what belongs in `$MERIDIAN_WORK_DIR`
- what belongs in `.meridian/fs/`

Subagents usually do not need this skill. They should follow the orchestrator's scoped prompt and the files they are given.

## Ownership

Work coordination is primary-owned.

- The orchestrator creates or attaches to real work items.
- The orchestrator updates work status as phases progress.
- The orchestrator decides what tracking artifacts to keep.
- Subagents should not mutate shared work state unless explicitly instructed.

If meaningful repo work is about to start and there is no active work item, create one first:

```bash
meridian work start "descriptive name"
```

If the work item already exists:

```bash
meridian work switch descriptive-name
```

## Work Model

Meridian separates work metadata from work-scoped scratch files:

- `.meridian/work-items/<slug>.json`
  - authoritative work-item metadata
  - status, description, created-at, and other Meridian-owned coordination state
- `.meridian/work/<slug>/`
  - optional work-scoped scratch/docs
  - design notes, decision logs, implementation logs, per-phase plans
- `.meridian/work-archive/<slug>/`
  - archived scratch/docs for completed work items
- `.meridian/fs/`
  - broader shared reference material not owned by one work item

The key rule is:

- `work-items` is authority
- `work` is work-scoped scratch
- `work-archive` is completed work scratch
- `fs` is broader shared reference space

## Status Management

Keep the current phase visible with `meridian work update --status ...`.

Recommended lifecycle:

```text
designing -> reviewing -> planning -> implementing -> done
```

Typical commands:

```bash
meridian work start "auth refactor"
meridian work update auth-refactor --status designing
meridian work update auth-refactor --status reviewing
meridian work update auth-refactor --status planning
meridian work update auth-refactor --status implementing
meridian work done auth-refactor
meridian work reopen auth-refactor
```

Use `meridian work clear` only when you intentionally want no active work item for the current session.
`work done` archives the scratch directory when present, and `work reopen` restores it.

## Artifact Placement

When a work item is active, `$MERIDIAN_WORK_DIR` points at its work-scoped scratch directory:

```bash
echo "$MERIDIAN_WORK_DIR"
# .meridian/work/auth-refactor/
```

Use `$MERIDIAN_WORK_DIR` for work-specific coordination artifacts such as:

- `overview.md`
- `decision-log.md`
- `implementation-log.md`
- `plan/phase-N-slug.md`
- ad hoc notes, diagrams, and phase-local scratch files

Use `.meridian/fs/` for broader shared reference material that is not specific to one work item, such as:

- cross-work-item reference docs
- shared architecture notes used by multiple efforts
- reusable datasets, fixtures, or reference outputs

If a file mainly exists to help one work item move forward, keep it in `$MERIDIAN_WORK_DIR`.
If it is shared project context across multiple work items, put it in `.meridian/fs/`.

## Standard Work Artifacts

Unless the task is trivial, the orchestrator should keep these artifacts under `$MERIDIAN_WORK_DIR`:

- `overview.md`
  - current design/approach
- `decision-log.md`
  - append-only design and planning decisions
- `implementation-log.md`
  - append-only findings, deferred issues, and coordination notes during execution
- `plan/`
  - per-phase specs when the work needs decomposition

These are conventions, not mandatory ceremony. Scale the artifact set to the size of the task.

## Handing Off To Other Skills

This skill owns work policy. Other skills own their craft:

- `design`
  - how to collaborate with the user on architecture and write design artifacts
- `plan-implementation`
  - how to decompose the design into phases
- `dev-workflow`
  - how to run the phase loop and staff agents
- `issue-tracking`
  - how to mirror findings into GitHub Issues

Those skills should assume the work item is already attached and should use the artifact placement rules from this skill rather than redefining them.
