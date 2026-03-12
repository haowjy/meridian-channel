---
name: meridian-work
description: Work item management for multi-agent coordination. Teaches when and how to create work items, write docs, and use $MERIDIAN_WORK_DIR.
---

# meridian-work

Work items track major efforts across spawns. Use them for tasks that involve multiple spawns, design docs, or coordination.

## When to use work items

- **Use for big efforts**: auth refactors, new features, multi-step migrations
- **Skip for small tasks**: quick fixes, one-off spawns - just use `--desc`

## Auto-generated work items

Every session starts with a work item. If you don't have one, meridian creates
one with a random name (e.g., `calm-brook-wren`). This ensures `$MERIDIAN_WORK_DIR`
is always available.

When you know what you're working on, name it:

```bash
meridian work start "auth refactor"
```

This renames the auto-generated item — all docs you've already written to
`$MERIDIAN_WORK_DIR` are preserved under the new name.

**Always use `$MERIDIAN_WORK_DIR` for design docs, plans, and notes.**
Never write loose files to `.meridian/work/`.

## Commands

```bash
meridian work                              # Dashboard - what's happening now
meridian work start "auth refactor"        # Create + set as active
meridian work list                         # List all work items
meridian work show auth-refactor           # Details + associated spawns
meridian work update auth-refactor --status "step 2"
meridian work done auth-refactor           # Mark complete
meridian work switch auth-refactor         # Change active work item
meridian work clear                        # Unset active work item
```

## Writing work item docs

Work items are directories. Add whatever docs help coordination:

```text
.meridian/work/auth-refactor/
  work.json        # Managed by meridian
  overview.md      # Your design doc
  auth-flow.mmd    # Diagrams
  plan/
    step-1.md
    step-2.md
```

Use `$MERIDIAN_WORK_DIR` to reference the work item directory in your prompts and scripts. Use `$MERIDIAN_WORK_ID` for the slug.

## Spawns and work items

Spawns inherit the active work item from the session:

```bash
meridian work start "auth refactor"
meridian spawn -m opus -p "implement step 2"
# spawn gets work_id: "auth-refactor"
```

Override with `--work`:

```bash
meridian spawn -m opus --work auth-refactor -p "implement step 2"
```
