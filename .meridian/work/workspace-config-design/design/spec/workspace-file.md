# WS-1: Workspace Topology File

## Context

Workspace configuration is a local topology declaration, not shared project policy. The file therefore has to encode locality in its name, stay optional for single-repo users, and remain minimal even though the internal model needs richer structure.

**Realized by:** `../architecture/paths-layer.md`, `../architecture/workspace-model.md`, `../architecture/surfacing-layer.md`.

## EARS Requirements

### WS-1.u1 — The workspace file name encodes locality

`The workspace topology file shall be named workspace.local.toml, shall be treated as local-only configuration, and shall not be introduced under the ambiguous name workspace.toml.`

### WS-1.u2 — Discovery order is explicit

`Workspace file discovery shall use MERIDIAN_WORKSPACE when that environment variable is set to an absolute path, and when that environment variable is unset shall use workspace.local.toml located next to the active .meridian/ directory when that file exists, and otherwise shall treat workspace topology as absent.`

### WS-1.u3 — The v1 schema stays minimal and topology-only

`The v1 user-facing workspace file schema shall use [[context-roots]] entries with required path and optional enabled fields, shall not contain a [settings] table, and shall default enabled to true when omitted.`

### WS-1.s1 — Absent workspace file means zero added behavior

`While no workspace file is present, Meridian shall behave as a single-repository installation and shall not emit workspace warnings or prompts.`

### WS-1.e1 — Default init creates a minimal file with commented examples

`When workspace init runs without a source manifest, Meridian shall create a minimal workspace.local.toml containing commented examples rather than active roots.`

### WS-1.e2 — `workspace init --from mars.toml` is disabled by default

`When workspace init --from mars.toml emits starter entries, Meridian shall emit commented context-root examples whose path value is empty, whose enabled value is false in the commented example, whose source-package canonical org/repo identifier appears in nearby comments, and which do not include a filesystem-path suggestion derived from any heuristic.`

### WS-1.e3 — Unknown keys are preserved and surfaced

`When Meridian parses workspace.local.toml and encounters unknown keys, Meridian shall preserve those keys for forward compatibility and shall surface them as warnings rather than dropping them or treating them as silent debug-only metadata.`

### WS-1.e4 — Broken workspace overrides stay absent but advisory

`When MERIDIAN_WORKSPACE is set to an absolute path that does not exist, Meridian shall treat workspace topology as absent for that invocation, shall not fall through to default workspace-file discovery, and shall emit a per-invocation advisory that the override target is missing.`

### WS-1.e5 — Relative workspace overrides are rejected explicitly

`When MERIDIAN_WORKSPACE is set to a non-absolute path, Meridian shall treat workspace topology as absent for that invocation, shall not fall through to default workspace-file discovery, and shall emit a per-invocation advisory that only absolute override paths are supported in v1.`

### WS-1.c1 — Invalid workspace files are fatal only on workspace-dependent commands

`While workspace.local.toml is syntactically invalid or violates schema requirements, commands that require workspace-derived directories shall fail before harness launch, and commands that only inspect state shall continue and surface the invalid status.`

## Non-Requirement Edge Cases

- **No auto-detection of local checkouts.** Generated paths from `--from mars.toml` are starter material, not discovered facts.
- **No per-harness subsets in v1.** The file declares one root set for all supporting harnesses.
