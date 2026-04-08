# Harness Overview

> What this is: the harness-facing half of the shell architecture.
>
> What this is not: the frontend protocol or package-loading story.

Back up to [../overview.md](../overview.md).

## 1. Role

The harness layer hides Claude/Codex/OpenCode transport differences behind one
session-lived adapter boundary. The shell depends on that boundary, not on any
concrete wire format.

## 2. V0 Reality

- **Live adapter:** Claude only.
- **Tier-1 design targets:** Claude, Codex app-server, and OpenCode.
- **Why this matters:** the abstraction must not bake Claude-specific
  assumptions into turn flow, tool resumption, or mid-turn steering.

## 3. Published Seams

- [abstraction.md](./abstraction.md) defines the adapter responsibilities and
  normalized command surface.
- [adapters.md](./adapters.md) records the concrete V0/V1 adapter posture.
- [mid-turn-steering.md](./mid-turn-steering.md) records the control semantics,
  including the required Claude verification spike.

## 4. Boundaries

- The harness layer owns process/session lifecycle and harness-native IO.
- The events layer owns normalized event schema and turn orchestration.
- The packaging layer owns prompt composition, `.agents/` materialization, and
  MCP config assembly.
- The execution layer owns how packaged MCP servers run locally.
