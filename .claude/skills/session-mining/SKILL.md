---
name: session-mining
description: "Workflow patterns for mining conversation history during dev work — recovering decisions from parent sessions, delegating bulk transcript reading, and discovering all sessions tied to a work item. Assumes the meridian session CLI is already understood (see meridian-cli)."
---

# session-mining

## Why Mining Matters

Design decisions, rejected alternatives, and discovered constraints often live in conversation instead of code or docs. Compaction makes that context expensive to recover later, so mine it before the next implementation or documentation step starts.

## Recover From the Parent Session First

Start from the spawning conversation. `$MERIDIAN_CHAT_ID` points to the parent session that launched the current spawn, and that parent context usually contains the highest-leverage decision history.

Use a narrow read first, then widen only if needed:

```bash
meridian session log "$MERIDIAN_CHAT_ID" --last 20
```

## Delegate Bulk Reading, Don't Inline It

When the question spans long histories or multiple sessions, spawn @explorer for transcript gathering and synthesis. That keeps your context window focused on synthesis and decision-making instead of raw transcript paging.

```bash
meridian spawn -a explorer --skills meridian-cli \
  -p "Mine session history for work item <id>. Summarize decisions, rejected options, constraints, and unresolved questions with session references."
```

If you are the @explorer, mine directly rather than spawning recursively.

## Discover Sessions Per Work Item

When work spans interruptions, reopenings, or multi-day execution, list all related sessions before mining. Reading only the current session misses prior decisions.

```bash
meridian work sessions <work_id> --all
```

## When to Skip Mining Entirely

Skip mining if the spawning prompt already includes the needed rationale, or if current design/plan artifacts already capture the decisions you need. Skim artifacts first, and mine only the gaps.
