# Interaction Layer

> What this is: the composite extension model introduced by D26.
>
> What this is not: the canonical mars manifest schema.

Back up to [overview.md](./overview.md).

## 1. Extension Shape

An interaction-layer extension is a **paired frontend+MCP package artifact**:

- a frontend bundle that renders a content block and captures user interaction,
- a paired MCP server that owns the corresponding local/domain behavior, and
- a registry entry that declares which block kinds the pair handles.

This replaces the old "interactive tool subprocess owned by the shell" model.

## 2. Bidirectional Flow

The interaction layer is load-bearing because the extension is not just a
renderer. It must support:

1. backend publishing a content block that mounts the extension,
2. user interaction inside that extension,
3. relay of those interactions back through the shell,
4. paired MCP handling, and
5. optional publication of new blocks or agent-visible events.

## 3. Agent Visibility

Not every user interaction should enter the agent transcript.

Two classes exist:

- **relay-only events:** local UI behavior such as viewport change or selection
  hover state,
- **agent-visible events:** state changes that should influence the next turn,
  such as confirmed landmark picks or approved ROI selection.

The paired MCP chooses which category a response belongs to.

## 4. V0 Examples

The shell itself ships none of these, but V0 must support packages that provide:

- a DICOM stack viewer,
- a 2D image viewer with region selection, and
- a 3D mesh viewer for inspection and picking.

## 5. Read Next

- [relay-protocol.md](./relay-protocol.md)
- [package-contract.md](./package-contract.md)
