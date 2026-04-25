# Codex TUI Passthrough

Meridian supports a managed primary Codex path instead of treating Codex as a pure black-box TUI.

## What It Does

For `meridian codex`, Meridian now:

1. Starts Codex `app-server`
2. Connects a managed observer
3. Starts or resumes the Codex thread with split instruction channels
4. Attaches the real Codex TUI with `codex resume <thread-id> --remote <ws-url>`

This gives Meridian a real Codex thread ID, managed startup telemetry, and hidden instruction delivery for the role/system tiers.

## Instruction Routing

Codex managed primary uses these channels:

- `baseInstructions`: agent/profile or role instructions
- `developerInstructions`: Meridian runtime instructions, skills, inventory, and reporting guidance
- `turn/start input`: the visible user turn

That keeps Meridian's system content out of the visible TUI prompt on managed paths.

## Fresh Session Bootstrap

Fresh Codex threads are not immediately attachable after `thread/start`. Codex needs at least one rollout materialized before `codex resume --remote ...` can attach.

Meridian handles that by sending a minimal bootstrap turn, then waiting only
until the Codex rollout file contains a matching `session_meta` entry for the
project cwd:

`Meridian bootstrap. Acknowledge readiness only; do not perform a user task.`

This bootstrap is intentionally small and deterministic. Meridian does **not** temporarily override Codex model/reasoning defaults for the bootstrap turn. The session should preserve Codex's own default or last-used settings.

## Why Fresh Start Feels Slower

Fresh `meridian codex` is slower than a black-box TUI launch because it does real managed work before the TUI appears:

- start `app-server`
- connect the observer
- create the thread
- run the bootstrap turn
- attach the TUI

Meridian shows compact startup telemetry for those phases so the delay is
legible:

- `Starting Codex app-server...`
- `Connecting managed observer...`
- `Creating fresh Codex thread...`
- `Materializing rollout...`
- `Attaching Codex TUI...`

## Attachability Gate

The important condition is:

`thread is attachable by the Codex TUI`

Today Meridian uses rollout materialization as that condition. It does not wait
for `turn/completed`, because full bootstrap response completion is not required
for TUI attach.

If Codex exposes an earlier observable signal like "thread attachable", Meridian should switch to that signal instead of:

- changing bootstrap wording
- lowering reasoning effort temporarily
- mutating user-visible Codex defaults

## Failure Behavior

Codex primary is managed-only. If managed startup fails, Meridian fails loudly instead of silently falling back to black-box Codex. This is deliberate: hidden instruction delivery and managed session tracking are the point of the command.

OpenCode behavior is different:

- primary resume uses managed attach
- other primary modes may still use black-box paths

## Related Files

- [codex_ws.py](../src/meridian/lib/harness/connections/codex_ws.py)
- [primary_attach.py](../src/meridian/lib/launch/process/primary_attach.py)
- [runner.py](../src/meridian/lib/launch/process/runner.py)
