# Packaging Overview

> What this is: the shell-facing view of mars packaging.
>
> What this is not: the canonical mars manifest schema.

Back up to [../overview.md](../overview.md).

## 1. Strategic Role

Packaging is the moat. The shell is valuable because mars materializes a bundle
of capabilities into a neutral runtime without hardcoding the vertical into the
shell itself.

## 2. V0 Item Kinds

V0 ships four kinds:

- `agent`
- `skill`
- `mcp_server`
- `interaction_layer_extension`

**D27:** treat this list as the current implementation, not the closed set.
Later kinds such as `cli_command` or `harness_adapter` must be mechanical
additions, not schema rewrites.

## 3. Canonical Schema Location

Do not restate the mars manifest schema in this tree. The canonical work item
for that remains:

- [../../../mars-mcp-packaging/requirements.md](../../../mars-mcp-packaging/requirements.md)

This design tree only records the shell-facing expectations from that work.

## 4. Wire Contract

**Binding version for shell V0:** `mars-manifest@0.x` pre-release, pinned at
shell V0 release time.

**Compatibility rule:** additive-only within the pinned V0 binding. Breaking
manifest changes require an explicit shell rebind rather than silent drift.

**Canonical source-of-truth:** the mars manifest contract lives in
[../../../mars-mcp-packaging/requirements.md](../../../mars-mcp-packaging/requirements.md);
this tree only records the shell-facing binding and expectations.

## 5. Shell-Facing Docs

- [agent-loading.md](./agent-loading.md) covers how `.agents/` materialization
  becomes a shell session.
- [../extensions/package-contract.md](../extensions/package-contract.md) covers
  the extension-facing slice of the manifest.
