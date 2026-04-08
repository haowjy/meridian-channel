# Events Overview

> What this is: the event and turn-flow boundary that keeps adapters, frontend,
> and extensions in sync.
>
> What this is not: the transport details of any specific harness.

Back up to [../overview.md](../overview.md).

## 1. Role

The events subsystem publishes the shell's canonical runtime contract:

- the **normalized schema** between harness adapters and backend orchestration,
- the **turn flow** that routes user input, tool execution, extension traffic,
  and results, and
- the **single-session V0 rules** for reconnect and secondary observers.

## 2. Design Rules

- The normalized schema is canonical. Wire docs derive from it.
- The translator stays rename-and-wrap only; it does not invent lifecycle
  edges, IDs, or attachment carriers.
- V0 has one active session per shell process.
- V0 second-tab behavior is read-only observer, not peer controller.

## 3. Published Docs

- [normalized-schema.md](./normalized-schema.md) is the canonical contract.
- [flow.md](./flow.md) is the runtime narrative built on that contract.
