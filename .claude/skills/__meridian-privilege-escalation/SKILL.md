---
name: __meridian-privilege-escalation
description: How to escalate agent permissions in meridian when a spawn hits capability limits — sandbox tiers, approval modes, model/harness switching, and per-spawn overrides. Use when a spawned agent fails because of sandbox restrictions, missing tools, harness limitations, or insufficient permissions, and you need to change the spawn configuration to unblock it.
---

# Privilege Escalation

Meridian agents run with constrained permissions by default — sandboxed filesystems, restricted tools, harness-specific limitations. When a spawn can't complete its task because of these constraints, you can escalate permissions per-spawn without changing the agent profile.

## Escalation Discipline

Prefer the least-privilege escalation that unblocks the task. Try targeted fixes first (`--sandbox full-access`, `--add-dir`, `--approval auto`) before broad overrides (`--approval yolo`, `--sandbox unrestricted`). Broad overrides disable safety checks entirely — if you're reaching for `yolo` or `unrestricted`, surface the situation to the user first and let them approve the escalation. An autonomous agent silently granting itself maximum permissions defeats the purpose of having tiers.

## Sandbox Tiers (Codex only)

The `--sandbox` flag controls Codex's process sandboxing — filesystem, network, and process isolation. Other harnesses (Claude, OpenCode) don't have sandbox tiers; see Approval Modes and Model/Harness Switching below for how to escalate permissions on those.

Tiers from most to least restrictive:

| Tier | What it allows |
|---|---|
| `read-only` | Read files only. No writes, no process execution. |
| `workspace-write` | Read/write within the workspace. No network listeners, no access outside project. |
| `full-access` | Full filesystem and process access. |
| `danger-full-access` | Like full-access with reduced safety checks. |
| `unrestricted` | No sandbox restrictions. |

Override per-spawn:
```bash
meridian spawn -a coder --sandbox full-access -p "Run integration tests that bind to localhost..."
```

Agent profiles set a default tier (e.g. `sandbox: workspace-write`). The `--sandbox` flag overrides it for that specific spawn only. The tier passes through directly to Codex's `--sandbox` flag.

## Approval Modes

The `--approval` flag controls how the harness handles tool-call approvals:

| Mode | Behavior |
|---|---|
| `default` | Harness decides (each harness has its own default policy). |
| `confirm` | User approves each tool call. |
| `auto` | Auto-approve safe operations, prompt for dangerous ones. |
| `yolo` | Approve everything. No prompts. |

Override per-spawn:
```bash
meridian spawn -a coder --approval auto -p "..."
meridian spawn -a coder --approval yolo -p "..."   # use sparingly
```

## Model/Harness Switching

Different models route to different harnesses, and each harness has different capability profiles. Switching the model can bypass harness-level restrictions entirely:

```bash
# Some harnesses have sandboxes that restrict network binding
meridian spawn -a coder -m <sandboxed-model> -p "..."

# Switching to a harness without sandbox restrictions sidesteps the issue
meridian spawn -a coder -m <unsandboxed-model> -p "..."
```

Run `meridian models list` to see which models route to which harness.

## Common Escalation Scenarios

**"Can't bind to a port / start a server"**
On Codex: sandbox restricts network listeners → `--sandbox full-access` or higher.
On Claude: not sandbox-restricted → check if the tool is in the allowedTools list, or use `--approval auto`.

**"Can't write files outside workspace"**
On Codex: sandbox restricts filesystem scope → `--sandbox full-access` for that spawn.
On Claude: use `--add-dir <path>` if you know the specific directory needed. If you don't know the directory upfront, escalate to the user — they can approve `--approval yolo` for that spawn.

**"Can't access the network / fetch URLs"**
On Codex: sandbox or tool restriction → ensure WebFetch/WebSearch are in the agent's tools list, or escalate sandbox.
On Claude: ensure the agent profile includes WebFetch/WebSearch tools.

**"Permission denied on tool call"** — approval mode is blocking.
→ `--approval auto` first. If that's not enough, surface to the user before using `--approval yolo`.

**"Context too small for the task"** — model limitation.
→ Switch to a model with a larger context window via `-m`.
