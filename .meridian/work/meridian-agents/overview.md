# Meridian Skills Coordination Workflows — Design

## Purpose

Meridian core provides shared coordination state. `meridian-skills` provides optional, opinionated workflows that tell agents how to use that state well.

This split keeps Meridian focused on mechanism and lets users choose their own collaboration policy.

## Boundary

Meridian core owns:

- work-item metadata under `.meridian/work-items/`
- work-scoped scratch docs and notes under `.meridian/work/<id>/`
- broader shared reference docs under `.meridian/fs/`
- session and spawn metadata such as `active_work_id`, `work_id`, and `desc`
- commands that surface coordination state, such as `meridian work` and `meridian spawn show`

`meridian-skills` owns:

- preflight coordination behavior for agents
- conventions for reading and updating work docs
- shared-worktree versus isolated-worktree policy
- branch or worktree lifecycle management when a workflow uses isolation
- merge, review, and handoff conventions
- optional workflow-specific metadata that core does not interpret

## Non-Goals

- `meridian-skills` is not one canonical workflow for all users.
- Meridian core should not need a schema or command change for every workflow variant.
- Skills should not redefine or fork the core coordination primitives that Meridian already owns.

## Workflow Families

Different skills may implement different collaboration models on top of the same Meridian state:

- shared worktree with coordination norms and strong anti-revert guidance
- shared worktree with dynamic claims or notes as scope becomes clearer
- isolated branch or worktree for collision-prone tasks, with later merge or rebase
- review-gated workflows where agents stage work for human or agent approval before integration

Meridian should not declare one of these to be the only supported model.

## State Consumption

Coordination skills should read the existing Meridian surface area rather than inventing a parallel registry:

- `.meridian/work-items/<id>.json` for authoritative work-item metadata
- `.meridian/work/<id>/` for work-scoped task docs, plans, and scratch notes
- `.meridian/fs/` for broader shared project context and long-lived reference docs
- session context for the active work item when present
- spawn metadata for who is currently working on what

When a workflow needs extra state, prefer skill-owned files or metadata that reference core work ids instead of extending the core model prematurely.

## Optional Metadata

Some workflows may want to attach extra details such as:

- isolation mode
- branch name
- worktree path
- merge target
- handoff or review status

These are workflow-policy concerns. Skills may record them, but Meridian core should preserve a clean boundary and avoid interpreting them unless a later product need proves they belong in the core model.

## Relationship to `meridian-work`

[`../meridian-work/overview.md`](../meridian-work/overview.md) defines the core coordination model. This document defines where opinionated workflows belong.

If this design area grows, keep `overview.md` as the entry point and split detailed workflow variants into additional files within this folder.
