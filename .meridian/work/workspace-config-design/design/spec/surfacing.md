# SURF-1: Workspace and Config State Surfacing

## Context

The previous design failed by hiding important behavior changes behind silent no-ops or chatty warnings. Surfacing must answer two questions cleanly: "what state am I in?" and "will my roots actually apply to this harness?"

**Realized by:** `../architecture/workspace-model.md`, `../architecture/surfacing-layer.md`, `../architecture/harness-integration.md`.

## EARS Requirements

### SURF-1.u1 — `config show` exposes a minimal structured workspace summary

`config show --json shall expose workspace as {status, path, roots: {count, enabled, missing}, harness_support: {claude, codex, opencode}}, and text output shall expose the same facts as flat grep-friendly key-value lines.`

### SURF-1.e1 — Inspection commands continue across invalid workspace files

`When workspace.local.toml is invalid, inspection commands such as config show and doctor shall continue running and shall surface workspace.status = invalid together with the validation findings.`

### SURF-1.e2 — Missing roots and unknown keys are surfaced per invocation

`When workspace.local.toml contains missing roots or unknown keys, doctor and config show shall surface those findings on every invocation that inspects workspace state, without requiring persistent suppression state.`

### SURF-1.e3 — (deleted)

Reserved tombstone to keep downstream references stable after prior-round surfacing reshapes removed the old `e3` slot.

### SURF-1.e4 — Spawn-time missing-root noise stays out of the default lane

`When a launch encounters configured workspace roots that are missing on disk, Meridian shall keep those findings out of the default spawn warning lane and shall expose them through config show, doctor, and debug-level launch diagnostics instead.`

### SURF-1.e5 — Applicability downgrades are explicit

`When the selected harness or sandbox will ignore or reject workspace-root injection for the current launch, Meridian shall emit an explicit applicability diagnostic for that invocation rather than silently behaving as though workspace roots were active.`

### SURF-1.e6 — Broken workspace overrides are surfaced across inspection commands

`When MERIDIAN_WORKSPACE is set to a broken override value, such as a missing absolute path or a non-absolute path, config show and doctor shall surface an actionable advisory for that invocation stating that workspace topology is absent because the explicit override could not be used.`

Note: the launch warning lane is not included because broken overrides produce `workspace.status = absent`, and absent workspace means zero workspace-dependent launch behavior (per WS-1.s1). The advisory surfaces pre-launch through the inspection tools where users check workspace health.

## Non-Requirement Edge Cases

- **No warning flood for healthy single-repo users.** `workspace.status = absent` is a quiet state.
- **No hidden JSON shape creep.** Additional detail belongs in warnings/diagnostics, not in a bloated replacement for the minimal workspace summary.
