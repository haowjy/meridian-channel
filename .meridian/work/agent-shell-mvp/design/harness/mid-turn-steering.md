# Mid-Turn Steering

> What this is: the published control semantics for delivering user input to a
> running turn.
>
> What this is not: a guarantee that every V0 adapter exposes the same user
> affordance.

Back up to [overview.md](./overview.md).

## 1. Why This Seam Exists

Mid-turn steering stays a first-class seam because it is part of the platform's
defining behavior, but D28 still applies: the seam must be real without forcing
the Claude V0 implementation to pretend reverse-engineered behavior is proven.

## 2. Declared Modes

| Mode | Meaning | V0/V1 user hint |
|---|---|---|
| `queue` | message is queued for the next safe turn boundary | "Message will be applied next turn boundary." |
| `interrupt_restart` | running turn is interrupted and restarted with the new message | "Current turn will be interrupted." |
| `http_post` | message is posted into the live session | no special warning |
| `none` | the seam exists but the adapter does not offer it in this build | composer disabled while turn active |

The frontend and CLI branch on the mode value, not on a boolean.

## 3. Claude Verification Spike

**H1 disposition:** Claude queue mode requires a **Phase 1.5 verification
spike** before the V0 adapter may declare `mid_turn_injection="queue"`.

The spike must prove all three cases on a real `claude --input-format
stream-json` subprocess:

1. initial handshake still behaves as expected,
2. a second `user` frame during a tool-call window is accepted, and
3. a second `user` frame during text streaming is accepted or rejected in a
   predictable way.

If the spike fails, Claude V0 falls back to `mid_turn_injection="none"`. The
shell contract stays intact; only the capability declaration changes.

TODO(H1/D28): run the Phase 1.5 Claude stream-json verification spike before
locking `mid_turn_injection="queue"` into the V0 adapter declaration.

## 4. V0 Surfaces

- **Frontend:** `inject_user_message` is a first-class command, but the composer
  only enables it mid-turn when the active adapter mode is not `none`.
- **CLI:** a future `meridian spawn inject` consumer can reuse the same semantic
  enum, but Q7 itself remains open.
- **Turn orchestration:** `TurnOrchestrator` never contains harness-native
  branching. It invokes `inject_user_message` and reads the declared mode for
  user-facing messaging only.

## 5. Non-Goals

- Do not promise a single UX across all harnesses.
- Do not model approval gating here.
- Do not use this seam to keep shell-owned domain processes alive; those moved
  behind packaged MCP servers.
