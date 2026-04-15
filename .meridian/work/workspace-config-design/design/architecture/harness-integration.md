# A04: Harness Integration

## Summary

Workspace topology is policy. Granting one harness access to those roots is
mechanism. The boundary is a harness-owned `HarnessWorkspaceProjection`
contract: launch code computes the ordered set of enabled existing roots once,
asks the selected adapter to project them, then merges the returned args/env and
surfaces the returned diagnostics without branching on harness-specific
mechanics.

## Realizes

- `../spec/context-root-injection.md` — `CTX-1.u1`, `CTX-1.e1`, `CTX-1.c1`, `CTX-1.e2`, `CTX-1.w1`, `CTX-1.w2`
- `../spec/surfacing.md` — `SURF-1.u1`, `SURF-1.e5`

## Current State

- Adapter contracts stop at `resolve_launch_spec()` and `preflight()` in
  `src/meridian/lib/harness/adapter.py:224-247`.
- Claude injects `--add-dir` inline during preflight in
  `src/meridian/lib/harness/claude_preflight.py:120-166`.
- Codex command projection has no workspace-root seam; it appends
  `spec.extra_args` directly in
  `src/meridian/lib/harness/projections/project_codex_subprocess.py:189-227`.
- OpenCode command projection likewise has no workspace-root seam; it only
  projects flags and passthrough args in
  `src/meridian/lib/harness/projections/project_opencode_subprocess.py:83-160`.
- Launch assembly has one shared merge point already:
  `src/meridian/lib/launch/context.py:148-223` builds preflight output,
  `SpawnParams`, resolved launch spec, and merged env for every subprocess
  harness.

The missing piece is not another shared `add_dirs` list. The missing piece is a
harness-owned projection interface that can represent both direct CLI args and
non-CLI mechanisms such as OpenCode config overlays.

## Target State

### Ordered-root planner

`src/meridian/lib/launch/context_roots.py` is the only place that decides which
workspace roots participate in one launch and in what order.

Responsibilities:

- Start from `WorkspaceSnapshot`.
- Keep only roots that are `enabled` and `exists`.
- Preserve declaration order from `workspace.local.toml`.
- Enforce the fixed ordering rule:
  `user passthrough -> projection-managed -> workspace-emitted`.
- Hand the resulting ordered roots plus launch context to the selected adapter.

The launch layer owns ordering. Adapters own mechanism.

### Projection types

`src/meridian/lib/harness/workspace_projection.py` owns the transport-neutral
types.

```python
type HarnessWorkspaceSupport = (
    "active:add_dir"
    | "active:permission_allowlist"
    | "ignored:read_only_sandbox"
    | f"unsupported:{reason}"
)


@dataclass(frozen=True)
class HarnessWorkspaceProjection:
    applicability: HarnessWorkspaceSupport
    extra_args: tuple[str, ...] = ()
    config_overlay: Mapping[str, object] | None = None
    env_additions: Mapping[str, str] = MappingProxyType({})
    diagnostics: tuple[str, ...] = ()
```

`config_overlay` stays in the contract even when the transport is environment
based. That keeps the semantic patch inspectable in tests and diagnostics rather
than hiding it inside an opaque env string. `env_additions` carries the
adapter-owned transport materialization, so launch composition still merges data
without knowing how any harness encodes it.

### Adapter contract

Extend the subprocess-harness contract with one adapter-owned method:

```python
def project_workspace(
    self,
    *,
    roots: tuple[Path, ...],
    execution_cwd: Path,
    child_cwd: Path,
    spec: ResolvedLaunchSpec,
) -> HarnessWorkspaceProjection: ...
```

Why this shape:

- It matches the existing contract style in
  `src/meridian/lib/harness/adapter.py:224-247`: the adapter owns harness
  translation, not a global registry of special cases.
- `spec` provides the effective harness configuration already resolved by the
  adapter, including permission state needed for Codex read-only handling.
- `execution_cwd` and `child_cwd` keep Claude's existing child-worktree logic
  available without hardcoding Claude behavior into launch assembly.

### Launch composition

`src/meridian/lib/launch/context.py:148-223` remains the single merge point, but
workspace projection is inserted after `spec = harness.resolve_launch_spec(...)`
and before env construction.

Composition contract:

1. `context_roots.py` computes ordered enabled existing roots.
2. `harness.project_workspace(...)` returns one
   `HarnessWorkspaceProjection`.
3. `projection.extra_args` appends to the resolved spec's `extra_args` tail.
4. `projection.env_additions` merges with runtime, plan, and preflight env
   overrides before `build_harness_child_env(...)`.
5. `projection.config_overlay` is preserved for surfacing/tests and is the
   semantic source of any harness-specific transport already reflected in
   `env_additions`.
6. `projection.diagnostics` flows to `config show`, `doctor`, and the selected
   launch's warning/debug lanes.

The launch layer does not branch on Claude vs Codex vs OpenCode. It merges one
projection object.

## Per-Harness Projection

### Claude

Mechanism:

- One enabled existing workspace root projects to
  `("--add-dir", "<abs-path>")` in `extra_args`.
- `applicability = "active:add_dir"`.
- `config_overlay = None`.
- `env_additions = {}`.

Ordering:

- Existing preflight behavior remains the projection-managed middle section:
  user passthrough, then `execution_cwd`, then parent
  `additionalDirectories` from `.claude/settings*.json`
  (`src/meridian/lib/harness/claude_preflight.py:120-147`).
- Workspace roots append after those parent-forwarded directories.
- First-seen dedupe remains authoritative
  (`src/meridian/lib/launch/text_utils.py:8-19`), so explicit user
  `--add-dir` values stay first and survive dedupe.

Target result:

```text
<user passthrough --add-dir ...>
<projection-managed execution_cwd>
<projection-managed parent additionalDirectories>
<workspace-emitted roots>
```

### Codex

Mechanism:

- One enabled existing workspace root projects to
  `("--add-dir", "<abs-path>")` in `extra_args`.
- Normal case: `applicability = "active:add_dir"`.
- Read-only sandbox case:
  `applicability = "ignored:read_only_sandbox"`,
  `extra_args = ()`,
  diagnostic emitted for surfacing.

Reasoning:

- Codex already accepts `--add-dir` (`probe-evidence/probes.md §1`).
- Its permission resolver already determines the effective sandbox mode in
  `src/meridian/lib/harness/projections/project_codex_subprocess.py:150-163`.
- The current subprocess projection appends `spec.extra_args` directly at
  `src/meridian/lib/harness/projections/project_codex_subprocess.py:219`;
  workspace projection appends after that tail so explicit user passthrough
  stays first under first-seen dedupe semantics.

Target result:

```text
<user passthrough --add-dir ...>
<workspace-emitted roots, unless read-only sandbox>
```

### OpenCode

Mechanism:

- OpenCode does not have `--add-dir` parity. Evidence:
  `.meridian/work/workspace-config-design/opencode-probe-findings.md`.
- Meridian projects enabled existing workspace roots into:

```json
{
  "permission": {
    "external_directory": [
      "/abs/root-1",
      "/abs/root-2"
    ]
  }
}
```

- `config_overlay` carries that semantic patch.
- `env_additions` carries the transport materialization:
  `{"OPENCODE_CONFIG_CONTENT": "<serialized-json>"}`.
- `applicability = "active:permission_allowlist"`.

Semantic gap:

- This is day-1 support, not fake `--add-dir` parity.
- OpenCode's native file tools gain access to the extra roots, but the harness
  does not surface them as named workspace roots in its UX.
- The roots behave like extra allowlisted directories beside the primary project
  root, not like a visible multi-root workspace list.

Alternative rejected:

- MCP filesystem servers were considered but rejected for day-1 support because
  they change the interaction model for extra roots instead of extending the
  same native file-tool path the primary root already uses
  (`opencode-probe-findings.md §4` and `§8`).

## Applicability Contract

`HarnessWorkspaceSupport` values are precise because surfacing depends on them.

| Value | Meaning | Expected harnesses |
|---|---|---|
| `active:add_dir` | Workspace roots are projected as repeated `--add-dir` args. | Claude, Codex |
| `active:permission_allowlist` | Workspace roots are projected through a config overlay that grants file-tool access. | OpenCode |
| `ignored:read_only_sandbox` | Harness selected a mode where workspace projection is inert for this launch. | Codex read-only sandbox |
| `unsupported:<reason>` | Harness has no workspace-root mechanism yet. | future harnesses only |

`unsupported:*` remains forward-looking even though day-1 support now covers the
three in-scope harnesses. Future harness additions should not need a spec
rewrite to surface their unsupported state honestly.

## Diagnostics

Projection diagnostics are per-invocation findings emitted by the adapter.

Required cases:

- Codex read-only sandbox ignored-state diagnostic.
- Future `unsupported:*` diagnostic with reason.
- Optional debug diagnostic when OpenCode delivered a permission-allowlist
  overlay instead of direct workspace-root UX.

Missing roots are not projection diagnostics. They are snapshot findings owned
by `WorkspaceSnapshot` and surfaced by the surfacing layer.

## Resolved Behaviors

- Per D15, if a parent environment already sets `OPENCODE_CONFIG_CONTENT`, the
  OpenCode adapter skips workspace projection and records a
  `HarnessWorkspaceProjection.diagnostics` entry for that invocation
  (`workspace_projection_suppressed_parent_opencode_config_content`). The
  parent environment value wins; Meridian does not deep-merge or overwrite it.
- Per D16, subprocess and streaming launches use the same
  `HarnessWorkspaceProjection.env_additions` channel. Both paths reach
  `asyncio.create_subprocess_exec(..., env=env)`, so OpenCode workspace
  projection reaches the child process identically regardless of transport.
