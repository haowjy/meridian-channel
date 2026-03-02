# Improvements

UX and observability improvements.

## High

### IMP-1: Failure summary fields for spawn diagnostics
- **Source**: migration-notes UX observations
- **Description**: When a spawn hangs or fails, one-command diagnosis is weak. Add deterministic failure summary fields: `failure_reason`, timeout/cancel marker, last phase reached.
- **Direction**: Structured failure artifact emitted during finalization regardless of harness output.

### IMP-2: Stderr verbosity tiers
- **Source**: migration-notes p4 noise, UX observations
- **Description**: Raw harness chatter (session headers, chain markers, shell echoes, MCP startup, per-command timing) buries actionable signal. Split user-facing summary from debug verbosity.
- **Direction**: Default output shows `spawn_id`, `status`, `duration`, `exit_code`, concise failure reason. Verbose output (`--debug`) includes harness/provider headers, internal chain markers, echoed shell commands, timing chatter.

## Medium

### IMP-3: Spawn cancel command
- **Source**: migration-notes r2 weirdness
- **Description**: No `meridian spawn cancel <id>` command exists. Background spawns that hang require manual SIGINT via process list inspection.

### IMP-4: Heartbeat/progress for long spawns
- **Source**: migration-notes UX observations
- **Description**: Long-running spawns provide no feedback until completion. Add running heartbeat or progress summaries.

### IMP-5: Space-state rules at spawn entry
- **Source**: migration-notes UX observations
- **Description**: Space-state behavior is unclear from UX (closed vs active handling around spawn launch). Tighten and surface space-state rules at spawn entry point.

## Low

### IMP-6: Finish terminology cleanup (`run` → `spawn`)
- **Source**: migration-notes UX observations
- **Description**: `run` wording still appears in some help text and output while the command surface is `spawn`. Complete the rename across all user-facing strings.
