# Meridian Coordination Layer — Design

## Problem

Operators (human or agent) have no way to see what's actively being worked on across a project. `meridian spawn list` shows spawn lifecycle (status, duration, cost) but not *intent* — what is this spawn doing, and what bigger effort is it part of?

## Design Decisions

- **Designs are a core concept.** Meridian is a coordination layer — designs and plans are coordination. Opinionated, same level as spaces, spawns, reports, skills.
- **Designs are git tracked.** Valuable working documents. Visible in PRs alongside code. Delete when done; git history preserves them.
- **Designs are space-scoped.** Everything in meridian is space-scoped.
- **No locks.** Coordination through visibility, not mechanisms. Operators check `meridian work`, decide to wait or proceed.
- **Single worktree.** All agents work in the same branch. Aggressive refactoring makes merges too painful.
- **Storage abstraction.** Local files today. Interface should support a managed service later.
- **`fs/` is the escape hatch.** Freeform, tracked, agent-managed. For stuff that doesn't fit into designs.

## Space Directory Layout

```
.meridian/.spaces/<space-id>/
  designs/          # git tracked — structured, meridian-managed
    auth-refactor/
      design.json
      overview.md
      auth-flow.mmd
      plan/
        step-1.md
        step-2.md
  fs/               # git tracked — freeform, agent-managed
  spawns/           # gitignored — ephemeral runtime state
    p5/
      params.json
      prompt.md
      stderr.log
      report.md
  space.json        # gitignored
  spawns.jsonl      # gitignored
  sessions.jsonl    # gitignored
```

### .gitignore strategy

Ignore everything in `.meridian/` except `designs/` and `fs/`:

```gitignore
.meridian/.spaces/*/spawns/
.meridian/.spaces/*/space.json
.meridian/.spaces/*/*.jsonl
```

## Designs

Each design is a directory with a `design.json` and freeform files:

```json
{
  "name": "auth-refactor",
  "description": "Extract session logic and add new middleware",
  "status": "implementing step 2",
  "created_at": "2026-03-08T..."
}
```

- `status` is a free-form string — operator sets whatever makes sense
- Can contain anything: markdown, mermaid diagrams, code snippets
- Plans live inside as `plan/` subdirectory when needed
- Designs are living documents — start rough, refine over time

### Active Design (per operator session)

Each operator session is associated with one design at a time. Spawns automatically grouped under it.

```bash
meridian design start "auth refactor"     # create + set as active
meridian design set auth-refactor         # switch to existing design
meridian design unset                     # clear active design
```

Sets `$MERIDIAN_DESIGN_PATH`. Optional — spawns without a design show up ungrouped.

## Spawn Changes

### Prompt storage

Full prompt stored per spawn:

```
spawns/p5/prompt.md     # full prompt text
spawns/p5/params.json   # metadata including description
```

### Description

Required short label on spawn create:

```bash
meridian spawn -m opus --desc "Implement step 2" -p @prompt.md
```

## Commands

### `meridian design`

```bash
meridian design start "auth refactor"   # create + activate
meridian design set auth-refactor       # activate existing
meridian design unset                   # deactivate
meridian design list                    # list all designs
meridian design show auth-refactor      # show design detail
```

### `meridian work` (read-only coordination view)

```bash
meridian work                # what's happening right now
meridian work show p5        # full spawn detail (prompt, refs)
```

Output:

```
ACTIVE
  auth-refactor          implementing step 2
    p5  opus     Implement step 2
    p6  gpt-5.4  Review step 1

  spawn-visibility       drafting design
    p9  sonnet   Add prompt storage

  (no design)
    p12 opus     Fix off-by-one in spawn list
```

Grouped by design. Design status from `design.json`. No duration, cost, or operational details.

### `meridian spawn` (mostly unchanged)

Adds `--desc` flag and `prompt.md` storage.

## Skills (baked into core)

- **`meridian-design`** — teaches operators when/how to create designs, write docs, sketch diagrams, use `$MERIDIAN_DESIGN_PATH`
- **`meridian-plan`** — teaches operators how to break designs into steps in `plan/` subdirectory

## Coordination Flow

1. Operator runs `meridian work`
2. Sees what designs are active and who's working on them
3. If overlap — runs `meridian work show <spawn>` to read the full prompt
4. Decides to wait or proceed

Small tasks: just spawn with `--desc`, no design.
Big efforts: `meridian design start`, write docs, break into plan steps, coordinate spawns.

## Open Questions

- How does active design persist for sessions not launched via `meridian start`?
- Cross-space visibility: does `meridian work` aggregate across all spaces?
- What interface does the design store need for future backends?
