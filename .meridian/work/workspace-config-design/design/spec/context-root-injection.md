# CTX-1: Context-Root Injection

## Context

Workspace roots matter only if they reach harness launches predictably. The launch contract has to preserve explicit user intent, respect inherited parent context, and report unsupported or inert cases instead of pretending the roots were applied.

**Realized by:** `../architecture/workspace-model.md`, `../architecture/harness-integration.md`, `../architecture/surfacing-layer.md`.

## EARS Requirements

### CTX-1.u1 — Enabled existing roots apply to every supporting harness in v1

`Enabled workspace roots that exist on disk shall apply to every harness and sandbox combination that Meridian marks as supporting workspace injection in v1, and v1 shall not define per-harness root subsets.`

### CTX-1.e1 — Explicit user `--add-dir` wins over workspace defaults

`When the user supplies explicit --add-dir passthrough arguments, Meridian shall emit those explicit arguments before any workspace-emitted --add-dir arguments so explicit CLI intent wins under first-seen dedupe semantics.`

### CTX-1.c1 — Inherited and projection-managed directories keep precedence over workspace defaults

`While a harness projection already emits execution-derived directories or parent-forwarded additional directories, Meridian shall append workspace-emitted directories after those projection-managed directories rather than before them.`

### CTX-1.e2 — Missing configured roots are advisory and omitted from launch

`When an enabled workspace root does not exist on disk, Meridian shall omit that root from the emitted launch arguments and shall treat the condition as advisory rather than fatal.`

### CTX-1.w1 — Codex read-only sandbox is an ignored state, not a supported state

`Where the selected harness is codex and the effective sandbox mode is read-only, Meridian shall treat workspace-root injection as ignored for that launch and shall not silently claim that workspace roots are active.`

### CTX-1.w2 — Unsupported harnesses are surfaced, not silently skipped

`Where the selected harness does not implement workspace-root injection in v1, Meridian shall omit workspace-emitted directories for that harness and shall surface the unsupported state through diagnostics rather than silently skipping it.`

## Non-Requirement Edge Cases

- **No new harness-specific topology syntax in v1.** The same declared root set applies wherever support exists.
- **No hidden override of explicit CLI intent.** Workspace roots are defaults, not a stronger precedence layer than user passthrough.
- **`MERIDIAN_HARNESS_COMMAND` bypass stays a surfaced unsupported path.** Primary launches that bypass normal adapter composition are covered by `CTX-1.w2`, realized in the architecture layer as `unsupported:harness_command_bypass`.
