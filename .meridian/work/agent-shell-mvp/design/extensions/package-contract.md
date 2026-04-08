# Extension Package Contract

> What this is: the shell-facing slice of the package contract for
> interaction-layer extensions.
>
> What this is not: the canonical mars schema.

Back up to [overview.md](./overview.md).

## 1. Scope

This document intentionally does **not** redefine the mars manifest schema. The
canonical work item remains:

- [../../../mars-mcp-packaging/requirements.md](../../../mars-mcp-packaging/requirements.md)

This doc only records what the shell needs that schema to express.

## 2. Wire Contract

**Binding version for shell V0:** the composite extension manifest slice binds
to `mars-manifest@0.x` pre-release, pinned at shell V0 release time.

**Compatibility rule:** additive-only within the pinned V0 binding. Breaking
changes to extension packaging require an explicit shell rebind.

**Canonical source-of-truth:** the mars manifest contract lives in
[../../../mars-mcp-packaging/requirements.md](../../../mars-mcp-packaging/requirements.md);
this doc only records the shell-facing slice for `interaction_layer_extension`.

## 3. Shell-Facing Requirements

An interaction-layer extension must let the shell discover:

- a stable `extensionId`,
- one or more content-block kinds the extension handles,
- the frontend bundle entry for the browser-side component,
- how to launch the paired MCP server locally, and
- any relay capability declarations needed at mount time.

## 4. Illustrative Shape

Illustrative only, not canonical:

```yaml
kind: interaction_layer_extension
id: biomed.mesh-viewer
dispatch_kinds:
  - mesh.3d
frontend:
  entry: dist/mesh-viewer.js
mcp:
  command: uv
  args: ["run", "python", "-m", "biomed_mesh_viewer.server"]
```

## 5. Design Constraints

- The shell may consume generated registries instead of raw manifests.
- The package contract must compose with `agent`, `skill`, and `mcp_server`
  kinds without forcing packages to split one workflow across multiple installs.
- The contract must survive local-to-hosted continuity without changing
  extension authoring semantics.

TODO(D27): confirm the canonical `ItemKind` spelling and generated registry
shape in the separate mars-mcp-packaging work item rather than freezing it
implicitly in shell docs.
