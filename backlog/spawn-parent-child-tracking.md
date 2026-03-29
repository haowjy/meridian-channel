# Spawn Parent-Child Tracking

## Problem

The runtime propagates parent-child relationships (`MERIDIAN_PARENT_SPAWN_ID`, `RuntimeContext.parent_spawn_id`, event `"parent"` field, depth `"d"`), but `SpawnRecord` in the spawn store doesn't persist `parent_spawn_id`. The `meridian work` dashboard groups spawns flat by work item — no tree structure.

When an orchestrator spawns a sub-orchestrator (e.g., planning-orch → impl-orch → coder), the hierarchy is invisible in the dashboard. All spawns appear flat under the same work item.

## Desired Behavior

- `SpawnRecord` persists `parent_spawn_id` (materialized from start event)
- `meridian spawn show` displays parent if present
- `meridian work show` renders spawn tree (indent children under parents)
- `meridian spawn list` supports `--tree` or `--parent` filter

## Context

Motivated by splitting dev-orchestrator into a planning orchestrator (interactive) that spawns an implementation orchestrator (autonomous, long-running). Without parent-child visibility, monitoring multi-tier orchestration is blind.
