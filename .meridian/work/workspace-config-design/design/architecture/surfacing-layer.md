# A05: Surfacing Layer

## Summary

Workspace state has to be inspectable without turning `config show` into a dump of internal details. The target shape is a small structured summary plus per-invocation warnings and launch diagnostics driven by the same observed state used elsewhere.

## Realizes

- `../spec/surfacing.md` — `SURF-1.u1`, `SURF-1.e1`, `SURF-1.e2`, `SURF-1.e4`, `SURF-1.e5`, `SURF-1.e6`
- `../spec/context-root-injection.md` — `CTX-1.w1`, `CTX-1.w2`
- `../spec/workspace-file.md` — `WS-1.c1`

## Shared Builder

`src/meridian/lib/ops/config_surface.py` is the shared builder consumed by both `config show` and `doctor`. The same `WorkspaceSnapshot` flows into the same builder, which produces both the `config show` workspace section and the `doctor` workspace findings. This prevents the two surfaces from independently computing workspace state and diverging.

Both commands must call `config_surface.py` rather than re-deriving workspace or config findings from raw state.

## Workspace Summary Shape

`config show --json` grows one minimal section:

```json
{
  "workspace": {
    "status": "absent | valid | invalid",
    "path": "/abs/path/to/workspace.local.toml",
    "roots": {
      "count": 3,
      "enabled": 2,
      "missing": 1
    },
    "harness_support": {
      "claude": "active:add_dir",
      "codex": "active:add_dir | ignored:read_only_sandbox",
      "opencode": "active:permission_allowlist"
    }
  }
}
```

Text output stays flat:

```text
workspace.status = valid
workspace.path = /repo/workspace.local.toml
workspace.roots.count = 3
workspace.roots.enabled = 2
workspace.roots.missing = 1
workspace.harness_support.claude = active:add_dir
workspace.harness_support.codex = ignored:read_only_sandbox
workspace.harness_support.opencode = active:permission_allowlist
```

## Warning Channels

### `config show` and `doctor`

Per-invocation findings:

- invalid workspace file
- unknown workspace keys
- missing enabled workspace roots
- missing `MERIDIAN_WORKSPACE` override target
- non-absolute `MERIDIAN_WORKSPACE` override value
- ignored or unsupported harness applicability

These commands are the main user-facing place to inspect workspace health.

### Spawn-time diagnostics

- **Default lane:** fatal invalid workspace file; applicability downgrade that changes launch behavior for the selected harness/sandbox
- **Debug lane only:** missing roots and unknown keys
- **Not in the launch lane:** broken workspace overrides (missing target, non-absolute path). These produce `workspace.status = absent`, which per WS-1.s1 means zero workspace-dependent launch behavior — there is no launch-lane context to surface an advisory in. The advisory surfaces pre-launch through `config show` and `doctor` (SURF-1.e6).

This keeps noisy, often-expected filesystem variance out of the default spawn path while still making actual "your configured roots will not apply here" cases visible.

## Doctor Contract

`doctor` should report discrete findings keyed by stable codes rather than prose-only summaries:

- `workspace_invalid`
- `workspace_unknown_key`
- `workspace_missing_root`
- `workspace_override_missing`
- `workspace_override_non_absolute`
- `workspace_harness_ignored`
- `workspace_harness_unsupported`

## Design Notes

- The summary shape is intentionally small. Rich per-root details belong in warnings and doctor findings, not in the steady-state payload.
- `workspace.status = absent` remains the steady-state value for both quiet
  absence and broken overrides; the `workspace_override_missing` and
  `workspace_override_non_absolute` findings are what tell inspection and launch
  surfacing that the absence came from a broken explicit override rather than
  from "no file declared".
- No dedicated `workspace_harness_permission_allowlist` doctor code is added. `active:permission_allowlist` is a supported steady-state applicability value, not a defect finding; it belongs in the summary payload, not in the findings stream.
- `workspace.status = absent` is a healthy quiet state for single-repo users.

## Open Questions

None at the architecture level.
