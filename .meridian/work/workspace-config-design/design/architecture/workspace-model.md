# A03: Workspace Model

## Summary

The workspace file is local-only and user-facing, but the internal model cannot
be a flat `list[Path]` if launch ordering, applicability, and diagnostics are
meant to stay correct. The target shape keeps the user-facing TOML minimal while
splitting the internal model into three layers: parsed document, evaluated
snapshot, and harness-owned projection.

## Realizes

- `../spec/workspace-file.md` — `WS-1.u2`, `WS-1.u3`, `WS-1.s1`, `WS-1.e1`, `WS-1.e2`, `WS-1.e3`, `WS-1.e4`, `WS-1.e5`, `WS-1.c1`
- `../spec/context-root-injection.md` — `CTX-1.u1`, `CTX-1.e2`
- `../spec/surfacing.md` — `SURF-1.e1`, `SURF-1.e2`, `SURF-1.e6`

## Current State

- There is no workspace file or workspace read model in the current checkout.
- The prior round proposed a lossy `context_directories() -> list[Path]`
  abstraction, but reviewers rejected it because ordering and provenance matter
  to launch behavior (`prior-round-feedback.md:17-21`).
- Probe evidence confirmed that first-seen ordering is load-bearing anywhere
  dedupe happens (`probe-evidence/probes.md:20-47`).

## Target State

Use a minimal user-facing TOML schema:

```toml
[[context-roots]]
path = "../mars-agents"
enabled = true
```

The internal model is split into three types with distinct responsibilities. The
user-facing schema stays minimal; the internal types stay rich.

### `WorkspaceConfig` — parsed document only

```text
WorkspaceConfig
  path: Path
  context_roots: tuple[ContextRoot, ...]
  unknown_top_level_keys: tuple[str, ...]
  warnings: tuple[str, ...]
```

Contract:

- Represents a successfully parsed document.
- Does not evaluate filesystem existence or harness support.
- Unknown keys survive parsing and surface as warnings.

```text
ContextRoot
  path: str
  enabled: bool = True
  extra_keys: Mapping[str, object]
```

`extra_keys` preserves unknown per-entry keys for warnings and forward-compatible
round-tripping without expanding the v1 user schema.

### `WorkspaceSnapshot` — evaluated state

```text
WorkspaceStatus = absent | valid | invalid

WorkspaceSnapshot
  status: WorkspaceStatus
  path: Path | None
  absent_reason: none | override_missing | override_non_absolute
  roots: tuple[ResolvedContextRoot, ...]
  unknown_keys: tuple[str, ...]
  findings: tuple[str, ...]
  harness_support: Mapping[str, HarnessWorkspaceSupport]

ResolvedContextRoot
  declared_path: str
  resolved_path: Path
  enabled: bool
  exists: bool
```

Contract:

- Single shared inspection object for `config show`, `doctor`, and launch
  preparation.
- Built by evaluating a `WorkspaceConfig` against the filesystem and harness
  capability table.
- `status=invalid` keeps the file path and findings so inspection commands can
  continue.
- `status=absent` remains the top-level quiet state, while `absent_reason`
  distinguishes "no workspace file declared" from broken explicit override cases
  such as "MERIDIAN_WORKSPACE pointed at a missing file" or
  "MERIDIAN_WORKSPACE used a non-absolute path" without forcing surfacing code
  to re-read the environment.
- `roots` includes disabled and missing entries so diagnostics can report counts
  without reparsing.
- `harness_support` uses the richer applicability states defined in
  [harness-integration.md](harness-integration.md).

### `HarnessWorkspaceProjection` — harness-owned launch contract

See [harness-integration.md](harness-integration.md) for the adapter boundary and
per-harness mechanics. The workspace model owns the fact that this is the third
layer in the split.

```text
HarnessWorkspaceSupport =
  active:add_dir
  | active:permission_allowlist
  | ignored:read_only_sandbox
  | unsupported:<reason>

HarnessWorkspaceProjection
  applicability: HarnessWorkspaceSupport
  extra_args: tuple[str, ...]
  config_overlay: Mapping[str, object] | None
  env_additions: Mapping[str, str]
  diagnostics: tuple[str, ...]
```

Contract:

- Transport-neutral output from `src/meridian/lib/launch/context_roots.py` and
  the selected harness adapter.
- Replaces the prior `WorkspaceLaunchDirectives` idea, which was too tied to
  direct `--add-dir` emitters.
- Can represent direct CLI flags (Claude, Codex) and config/env-based access
  mechanisms (OpenCode) without changing the workspace parser or snapshot model.
- Keeps applicability and diagnostics attached to the projection itself rather
  than forcing the surfacing layer to re-derive them.

### Resolution rules

- Resolve relative root paths relative to the containing workspace file, not the
  process cwd.
- Preserve declaration order across all three layers.
- Preserve unknown keys at both file scope and root-entry scope so future
  versions can round-trip them.
- Treat enabled-but-missing roots as snapshot findings; omit them before
  projection.

### Validation tiers

| Condition | Status impact | Launch impact | Inspection impact |
|---|---|---|---|
| No env override and no file next to `.meridian/` | `absent` + `absent_reason=none` | no workspace behavior | no warnings |
| `MERIDIAN_WORKSPACE` points at a missing absolute-path file | `absent` + `absent_reason=override_missing` | no workspace behavior; no fallback to default discovery | advisory |
| `MERIDIAN_WORKSPACE` uses a non-absolute path | `absent` + `absent_reason=override_non_absolute` | no workspace behavior; no fallback to default discovery | advisory |
| Parse/schema error | `invalid` | fatal for workspace-dependent commands | surfaced, non-fatal |
| Unknown key | `valid` | non-fatal | warning |
| Enabled root missing on disk | `valid` | root omitted before projection | warning |

## Design Notes

- The user-facing schema stays minimal on purpose. The internal richness belongs
  in `ContextRoot.extra_keys`, `WorkspaceSnapshot`, and
  `HarnessWorkspaceProjection`, not in v1 TOML boilerplate.
- `workspace init --from mars.toml` emits starter entries as comments in the
  file; provenance is file convention, not a parsed field.
- Broken explicit overrides remain `workspace.status = absent` rather than
  `invalid` because Meridian can still run without workspace roots; the design
  makes the misconfiguration visible through findings instead of blocking launch.
- This model keeps the door open for future per-root tags or access metadata
  without having to redesign the parser around a flat list later.

## Open Questions

None at the workspace-model layer. Open transport questions live in
[harness-integration.md](harness-integration.md).
