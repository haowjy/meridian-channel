# Extensions Overview

> What this is: the package-driven interaction model beyond the shell's built-in
> renderers.
>
> What this is not: the mars manifest schema itself.

Back up to [../overview.md](../overview.md).

## 1. Core Idea

**D26:** V0 extensions are **interaction-layer pairs**:

- a frontend component that renders or captures user interaction, and
- a paired MCP server that owns the corresponding backend/domain behavior.

The shell sits in the middle and relays events. Browser code does not talk
directly to the MCP process.

## 2. Why Relay Matters

Relay is the seam that preserves the future hosted story. Direct browser→MCP
channels would bake local-only assumptions into extension authorship and make
hosted continuity harder later.

## 3. Docs

- [interaction-layer.md](./interaction-layer.md) defines the composite model.
- [relay-protocol.md](./relay-protocol.md) publishes the bidirectional wire
  contract.
- [package-contract.md](./package-contract.md) records the shell-facing package
  expectations and points to the separate mars work item for canonical schema.
