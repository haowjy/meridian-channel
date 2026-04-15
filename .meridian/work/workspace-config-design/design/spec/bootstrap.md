# BOOT-1: Bootstrap and Opt-In File Creation

## Context

The runtime state root and committed/local sibling files have different ownership. First-run bootstrap may create runtime state because the CLI needs it to function, but it must not surprise users by creating new policy files beside the active `.meridian/` that they never asked for.

**Realized by:** `../architecture/paths-layer.md`, `../architecture/config-loader.md`.

## EARS Requirements

### BOOT-1.u1 — Generic first-run bootstrap creates runtime state only

`On generic Meridian startup, Meridian shall create only the .meridian runtime directories and .meridian/.gitignore needed for local state, and shall not auto-create meridian.toml or workspace.local.toml in the same directory as the active .meridian/.`

### BOOT-1.e1 — `config init` creates root config only when explicitly requested

`When the user runs meridian config init, Meridian shall create meridian.toml in the same directory as the active .meridian/ if it is absent, and shall not scaffold .meridian/config.toml as the target project config.`

### BOOT-1.e2 — `workspace init` is the only creator of the workspace file

`When the user runs meridian workspace init, Meridian shall create workspace.local.toml as an opt-in local file, and no other generic Meridian command shall create workspace.local.toml implicitly.`

## Non-Requirement Edge Cases

- **No sibling-file creation on `spawn`, `doctor`, or unrelated commands.** Those commands may inspect state but do not opt the user into new files beside `.meridian/`.
- **No surprise rewrite on ordinary reads.** Committed config creation remains an explicit command.
