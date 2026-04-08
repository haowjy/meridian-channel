# Harness Adapters

> What this is: the concrete V0/V1 adapter posture after the correction pass.
>
> What this is not: a promise that all adapters ship in V0.

Back up to [overview.md](./overview.md).

## 1. V0 And V1 Posture

| Adapter | Runtime status | Design status | Notes |
|---|---|---|---|
| Claude Code | V0 live target | tier-1 | local shell validation harness |
| Codex app-server | V1 stub | tier-1 | stable core JSON-RPC stdio; not blocked on protocol risk |
| OpenCode | V1 stub | tier-1 | stable HTTP session API |

Implementation order after Claude is a product decision, not a protocol-risk
decision.

## 2. Claude V0

Claude boots with one authoritative initialization path:

- `--append-system-prompt` carries the composed system prompt
- `--mcp-config` carries tool and MCP availability
- `--input-format stream-json --output-format stream-json` carry the live
  control channel

The shell does **not** use `--agents` for session boot. That inconsistency is
closed in this pass.

Mid-turn queue mode is conditioned on the verification spike defined in
[mid-turn-steering.md](./mid-turn-steering.md). Until that spike passes, the
design must treat Claude queue mode as provisional, not assumed.

## 3. Codex V1

Codex uses `codex app-server` over stable JSON-RPC stdio. The load-bearing
correction from the prior pass is explicit:

- The old concern that Codex breaks a shell-owned persistent biomedical kernel
  is **moot**.
- The shell no longer owns that kernel.
- Domain behavior lives behind packaged MCP servers and interaction-layer
  extensions.

That means Codex only needs to interoperate with shell-owned coordination and
packaged MCP surfaces, which is the same architectural burden as Claude and
OpenCode.

## 4. OpenCode V1

OpenCode remains the cleanest protocol surface conceptually:

- session-oriented HTTP control,
- direct POST semantics for mid-turn messages, and
- straightforward capability expression.

The abstraction is still shaped to fit OpenCode cleanly even though Claude is
the only V0 implementation.

## 5. Capability Honesty

Adapters report what they do in this build. They do not advertise:

- future protocol potential,
- dormant resume paths,
- shell features that are only envisioned for the hosted runtime, or
- domain tools that moved out into packaged MCP servers.

## 6. Read Next

- [mid-turn-steering.md](./mid-turn-steering.md)
- [../events/flow.md](../events/flow.md)
