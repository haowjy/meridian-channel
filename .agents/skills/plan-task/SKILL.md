---
name: plan-task
description: Breaks the next task from a plan into an implementable task file. Use when decomposing a multi-step plan into ordered work units.
---

# Plan Task

Create the next implementable task from a plan.

## When Invoked

### Step 1: Read Inputs

Use these prompt variables:
- `{{PLAN_FILE}}` — source plan to read
- `{{TASKS_DIR}}` — runtime task directory (write outputs here)

### Step 2: Read Progress

Gather context on what is already completed:

1. Read `{{PLAN_FILE}}` and inspect status/phase tracking sections.
2. If `{{TASKS_DIR}}/progress.md` exists, read it for prior completed tasks.
3. If `{{TASKS_DIR}}/task.md` exists, use it as context for continuity.

### Step 3: Determine Completion

If all phases/steps in the plan are complete:
- Write **only** the text `ALL_DONE` to `{{TASKS_DIR}}/task.md`.
- Stop here.

### Step 4: Create Task File

Determine the next logical task from the plan.

Write `{{TASKS_DIR}}/task.md`. Include whatever structure makes sense, but the task file should give an implementing agent everything it needs:

- **Context**: why this task is next
- **Scope**: what to implement — files, functions, integration points
- **Acceptance criteria**: how to verify it's done
- **Constraints**: architectural limits, gotchas

A good task is **self-contained**: the codebase must be in a working state when done. Size is secondary — focus on logical completeness, not line count.
