# Agent Loading

> What this is: the shell-side loading path from mars materialization to a live
> session.
>
> What this is not: a new agent registry or a manifest schema definition.

Back up to [overview.md](./overview.md).

## 1. Inputs

The shell consumes generated mars materialization under `.agents/`:

- agent profiles,
- skill bodies,
- generated MCP launch/config data, and
- generated extension registry data.

This pass keeps `.agents/` as generated output. Source editing still happens in
package repos, not here.

## 2. SessionContext

The shell builds one `SessionContext` per active session containing:

- resolved agent profile,
- resolved skills,
- composed system prompt,
- selected harness id and model,
- generated MCP config,
- extension registry snapshot, and
- active work-item directory.

The shell reuses existing prompt composition and profile resolution machinery
where possible. It does not invent a second prompt-building path for sessions.

## 3. Claude Boot Path

**M3 disposition:** the authoritative Claude session boot path is:

- `--append-system-prompt`
- `--mcp-config`
- live stream-json IO

The shell does **not** use `--agents` for V0 session boot.

## 4. Package Composition

The loading path assumes one customer workflow may arrive as one package set
that includes:

- an agent,
- its skills,
- one or more MCP servers, and
- any interaction-layer extensions it requires.

That is the unit the shell should feel like it is mounting.

## 5. Shell-Mars Boundary

The shell consumes mars output through generated files and registries. It does
not import mars internals. The canonical shell↔mars contract remains in:

- [../../../mars-mcp-packaging/requirements.md](../../../mars-mcp-packaging/requirements.md)

## 6. Read Next

- [overview.md](./overview.md)
- [../harness/adapters.md](../harness/adapters.md)
- [../extensions/package-contract.md](../extensions/package-contract.md)
