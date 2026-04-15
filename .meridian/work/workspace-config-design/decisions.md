# Decisions Log — workspace-config (redesign round)

Round: fresh redesign after a unanimous 5-0 reject of the prior design. Requirements
(`requirements.md`) are unchanged. This file records the addressed-or-rejected mapping
against `prior-round-feedback.md` (findings F1–F19) plus the non-trivial design calls
made during this round.

Evidence citations point at `probe-evidence/probes.md` and the live meridian-cli
checkout. Spec and architecture IDs point at the files under `design/spec/` and
`design/architecture/`.

## Prior-round findings (F1–F19) mapping

Each row states: the finding, the design response (addressed vs rejected), the spec
and architecture leaves that encode the response, and the evidence basis.

### F1 — Codex CLI has `codex exec --add-dir`
**Status:** Addressed.
**Response:** Design commits to codex as a supported target in v1. Workspace roots
reach codex through `codex exec --add-dir` in the codex projection.
**Encoded in:** `design/spec/context-root-injection.md` (`CTX-1.u1`);
`design/architecture/harness-integration.md` (A04 "Codex" section);
`design/feasibility.md` FV-1.
**Evidence:** `probe-evidence/probes.md §1` — captured `codex exec --help` output on
codex-cli 0.120.0 showing `--add-dir <DIR>` flag.

### F2 — Mars owns model-alias resolution; no Meridian-side `models.toml` migration is justified
**Status:** Addressed by explicit out-of-scope.
**Response:** Design declares `models.toml` migration out of scope. No spec leaves
reference it. Refactor agenda has no model-alias entry.
**Encoded in:** `design/spec/config-location.md` "Non-Requirement Edge Cases" (no
`models.toml` migration); `design/feasibility.md` FV-3.
**Evidence:** `probe-evidence/probes.md §3` — `rg "models\.toml|models_merged"`
returns zero hits in `src/` and `tests/`; `lib/catalog/model_aliases.py:229`
references `.mars/models-merged.json` only.

### F3 — Meridian config commands bypass the loader's resolver
**Status:** Addressed with dedicated architecture leaf.
**Response:** Introduce one `ProjectConfigState` object shared by the settings
loader AND all five `config` subcommands AND runtime bootstrap AND diagnostics.
Half-migrations (loader-only) are explicitly forbidden.
**Encoded in:** `design/architecture/config-loader.md` (A02 "Command-family
consistency" section enumerates every consumer that must use the shared state);
`design/refactors.md` R02 (exit criteria: "One observed project-config state object
is shared by loader, config commands, bootstrap, and diagnostics. No command reads
from root while another writes to legacy.").
**Evidence:** `probe-evidence/probes.md §4` — enumerated call sites
`lib/ops/config.py:758, 777, 827, 846, 872` all call `_config_path` directly, never
`_resolve_project_toml`.

### F4 — Dedupe ordering inverted last-wins semantics
**Status:** Addressed with explicit pinned ordering.
**Response:** `dedupe_nonempty` is first-seen; design pins emission order as
`user passthrough → projection-managed (execution_cwd, parent additional) → workspace`
on the claude path and `user passthrough (spec.extra_args) → workspace` on the codex
path. Explicit CLI intent wins under first-seen dedupe.
**Encoded in:** `design/spec/context-root-injection.md` `CTX-1.e1` (explicit
`--add-dir` wins), `CTX-1.c1` (projection-managed and parent-forwarded roots keep
precedence over workspace defaults); `design/architecture/harness-integration.md`
A04 "Shared ordered-root planner" and the per-harness subsections;
`design/feasibility.md` FV-2.
**Evidence:** `probe-evidence/probes.md §2` (`lib/launch/text_utils.py:8-19`),
`§5` (claude preflight ordering at `lib/harness/claude_preflight.py:131-147`),
`§6` (codex projection at `lib/harness/projections/project_codex_subprocess.py:189-227`).

### F5 — Flat `list[Path]` abstraction loses ordering and provenance
**Status:** Addressed.
**Response:** User-facing TOML stays minimal (`[[context-roots]]` with `path`,
`enabled`). Internal model carries structured root entries, evaluated
existence/state, unknown keys, and per-harness applicability instead of collapsing
everything into a flat list. This is the "minimal schema, structured internal
model" split the reviewers asked for.
**Encoded in:** `design/spec/workspace-file.md` `WS-1.u3` (v1 schema minimal);
`design/architecture/workspace-model.md` (A03 "Target State" shows the
`WorkspaceRoot` shape).
**Evidence:** `prior-round-feedback.md:17-21` plus `probe-evidence/probes.md §2`
(order is load-bearing because downstream dedupe is first-seen).

### F6 — Silent harness no-op is a footgun
**Status:** Addressed with mandatory surfacing.
**Response:** Per-harness applicability is reported explicitly in `config show`
and `doctor`. Codex read-only sandbox is `ignored:read_only_sandbox`; opencode
is `active:permission_allowlist`; future unimplemented harnesses use
`unsupported:*`. No silent skip anywhere.
**Encoded in:** `design/spec/context-root-injection.md` `CTX-1.w1` (codex
read-only), `CTX-1.w2` (unsupported harnesses surface);
`design/spec/surfacing.md` `SURF-1.e5` (applicability downgrades are explicit),
`SURF-1.u1` (`config show` exposes `harness_support` map);
`design/architecture/harness-integration.md` A04 "Applicability reporting";
`design/architecture/surfacing-layer.md` A05 "Doctor Contract".

### F7 — RF-1 was drastically under-scoped
**Status:** Addressed with enumerated blast radius.
**Response:** `design/refactors.md` R02 enumerates every call site
(`lib/config/settings.py`, `lib/ops/config.py`, `lib/ops/runtime.py`,
`lib/ops/manifest.py`, `cli/main.py`, smoke tests, unit tests). Exit criteria
require simultaneous update of read/write/bootstrap/CLI-copy/tests.
**Encoded in:** `design/refactors.md` R02; `design/feasibility.md` FV-4.
**Evidence:** `probe-evidence/probes.md §4` — full enumerated list with line numbers.

### F8 — Root-file policy doesn't belong in `state/paths.py`
**Status:** Addressed.
**Response:** New `ProjectPaths` abstraction owns `meridian.toml`,
`workspace.local.toml`, `MERIDIAN_WORKSPACE` resolution, repo-root ignore policy.
`StatePaths` stays `.meridian`-scoped.
**Encoded in:** `design/architecture/paths-layer.md` (A01 "Ownership boundary"
table); `design/refactors.md` R01 (prep refactor, exit criteria explicit);
`design/feasibility.md` FV-5.
**Evidence:** `probe-evidence/probes.md §7` —
`lib/state/paths.py:21,33,93-128` shows `.meridian`-only scope.
**Rejected alternative:** Extending `StatePaths` to carry root-file fields —
rejected because it mixes repo-policy and state-root concerns and makes
`.meridian/.gitignore` the wrong owner of repo-root ignore policy.

### F9 — Auto-creating `meridian.toml` on first invocation violates progressive disclosure
**Status:** Addressed.
**Response:** Generic startup creates ONLY `.meridian/` runtime directories and
`.meridian/.gitignore`. `meridian.toml` is created only by explicit
`config init`. `workspace.local.toml` is created only by `workspace init`.
**Encoded in:** `design/spec/bootstrap.md` `BOOT-1.u1` (generic startup creates
runtime state only), `BOOT-1.e1` (init is the only root-config creator),
`BOOT-1.e2` (workspace init is the only workspace-file creator);
`design/feasibility.md` FV-6.
**Evidence:** `probe-evidence/probes.md §8` —
`lib/ops/config.py:737-763` currently auto-writes scaffold unconditionally via
`ensure_state_bootstrap_sync` called from `lib/ops/runtime.py:66`.

### F10 — "Fatal on parse error" is too blunt for inspection commands
**Status:** Addressed.
**Response:** Workspace-dependent commands (spawn, `workspace *`) fail before
launch on invalid workspace file; inspection commands (`config show`, `doctor`)
continue and surface `workspace.status = invalid`.
**Encoded in:** `design/spec/workspace-file.md` `WS-1.c1` (scoped fatality);
`design/spec/surfacing.md` `SURF-1.e1` (inspection commands continue);
`design/architecture/workspace-model.md` A03 "Validation tiers" table;
`design/architecture/surfacing-layer.md` A05.

### F11 — Warn-on-every-missing-path becomes spawn noise
**Status:** Addressed.
**Response:** Missing-root noise stays OUT of the default spawn lane; it surfaces
in `config show`, `doctor`, and debug-level launch diagnostics instead.
Applicability downgrades (actual launch-behavior changes) DO surface at default
level because those are not noise — they indicate the launch will behave
differently than the user expects.
**Encoded in:** `design/spec/surfacing.md` `SURF-1.e4` (spawn-time missing-root
noise stays out of the default lane), `SURF-1.e5` (applicability downgrades
are explicit); `design/architecture/surfacing-layer.md` A05 "Warning Channels"
split between default and debug lanes.

### F12 — Unknown-keys "debug only" hides config typos
**Status:** Addressed.
**Response:** Unknown keys are preserved for forward compatibility AND surfaced
as warnings in `doctor` and `config show`. Not debug-only.
**Encoded in:** `design/spec/workspace-file.md` `WS-1.e3`;
`design/spec/surfacing.md` `SURF-1.e2`;
`design/architecture/workspace-model.md` A03 (unknown-key handling in the model);
`design/architecture/surfacing-layer.md` A05 (`workspace_unknown_key` doctor code).

### F13 — `workspace init --from mars.toml` risks broken-by-default state
**Status:** Addressed.
**Response:** Default `workspace init` creates a file with commented examples
only. `workspace init --from mars.toml` emits each entry with `enabled = false`
and uses canonical `org/repo` identifiers (never personal filesystem paths).
**Encoded in:** `design/spec/workspace-file.md` `WS-1.e1` (default init commented
examples), `WS-1.e2` (`--from mars.toml` emits disabled entries with `org/repo`
identity); `design/architecture/workspace-model.md` design notes.

### F14 — `config show` needs a crisp minimal answer set
**Status:** Addressed.
**Response:** Explicit JSON shape pinned:
`{status, path, roots: {count, enabled, missing}, harness_support: {claude, codex, opencode}}`.
Text output stays flat and grep-friendly. Rich per-root detail lives in
warnings and doctor findings, not in the steady-state payload.
**Encoded in:** `design/spec/surfacing.md` `SURF-1.u1`;
`design/architecture/surfacing-layer.md` A05 "Workspace Summary Shape" (both
JSON and text forms shown).

### F15 — Gitignored `workspace.toml` violates monorepo convention
**Status:** Addressed. The file is `workspace.local.toml`.
**Response:** Filename encodes locality. The `.local` suffix is consistent with
`.env.local`, `mars.local.toml`, `compose.override.yaml` precedents cited by the
reviewer. `workspace.toml` (unsuffixed) is explicitly refused.
**Encoded in:** `design/spec/workspace-file.md` `WS-1.u1`;
`design/architecture/paths-layer.md` A01;
`design/feasibility.md` Open Questions §3 records the prior-art rationale.
**Rejected alternative:** `workspace.toml` under a gitignore rule — rejected
because across pnpm/npm/Yarn/Rush/Nx/Bazel/Go/Cargo/Bun/Deno, `workspace.*`
names mean committed team topology. A gitignored file under that name
mis-signals intent.

### F16 — `[context-roots]` naming is jargon-heavy
**Status:** Addressed (low priority acknowledged).
**Response:** Design commits to `[[context-roots]]` for consistency with
Meridian's existing "context" language (`MERIDIAN_CHAT_ID`, "context handoffs"
skill). Alternatives `[include-dirs]` / `[extra-dirs]` considered and rejected
on consistency grounds.
**Encoded in:** `design/spec/workspace-file.md` `WS-1.u3`;
`design/architecture/workspace-model.md` A03 (TOML schema example);
`design/feasibility.md` Open Questions §2 flags this as low-priority and
reversible if a reviewer insists.

### F17 — No sunset trigger for the dual-read fallback
**Status:** Obsolete per D8.
**Response:** No migration path exists. There is no dual-read fallback and no phase plan. Implementation breaks `.meridian/config.toml` without warning. Aggressive collapse is "no collapse required — no phases exist."

### F18 — "Emit a one-time advisory" is not implementable as specified
**Status:** Obsolete per D8.
**Response:** No legacy fallback means no migration advisory. The per-invocation advisory cadence question does not arise.

### F19 — `config migrate` idempotency underspecified for divergent files
**Status:** Obsolete per D8.
**Response:** No `config migrate` command exists. The question of four-case idempotency does not arise.

## Cross-cutting design calls

### D1 — Spec and architecture are two separate trees with explicit realizes/realized-by links
Spec leaves (`CFG-1`, `WS-1`, `CTX-1`, `SURF-1`, `BOOT-1`) are behavioral
contracts in EARS notation. Architecture leaves (`A01`–`A05`) are observational
— they describe the target shape implementation must preserve, not a step-by-step
plan. Each architecture leaf's `Realizes` section points at specific spec EARS
IDs. Each spec leaf's `Realized by` section points at architecture leaves.
Planning consumes both trees and the refactor agenda; it does not invent
structure the architecture tree did not declare.

### D2 — Repo-root file abstraction is a prep refactor, not a rename
R01 (`design/refactors.md`) creates `ProjectPaths` before R02 rewires the
command family. Doing the command-family rewire without the boundary split
first would either bloat `StatePaths` with repo-root concerns or create a
transient state where two layers both claim ownership of `meridian.toml`.
The sequencing is prep → rewire → observe.

### D3 — `context_directories()` abstraction is NOT introduced in v1
The prior design's single-consumer flat-list abstraction was rejected. The
replacement is an ordered-root planner plus `HarnessWorkspaceProjection`
(ordered, applicability-aware, transport-neutral). A separate shared direct
`--add-dir` emitter is still deferred until post-interface duplication actually
drifts. This follows the `dev-principles` rule "Leave two similar cases
duplicated. Extract at three."

### D4 — Historical unsupported stance is superseded
The earlier redesign sketch treated OpenCode as `unsupported`. That position is
superseded by D11 after the dedicated OpenCode probe landed. Keep this note only
so readers understand why older references may still mention
`unsupported:v1`.

### D5 — Migration detail decision is obsolete
This decision became obsolete once D8 removed migration from scope entirely.
Keep the slot for chronology only; there is no `config migrate` contract and no
`migration.md` leaf in the approved target-state package.

### D6 — `.meridian/.gitignore` `!config.toml` exception is scaffolding and is removed now
The exception exists today because `.meridian/` is otherwise fully gitignored
and `config.toml` was committed. With migration out of scope per D8, there is no
Phase C: the exception is removed in the target-state refactor so `.meridian/`
returns to the intended boundary of fully local/runtime state. R04
(`design/refactors.md`) owns this removal.

### D7 — Spec hierarchy size is deliberately small
Five spec subsystems (`CFG-1`, `WS-1`, `CTX-1`, `SURF-1`, `BOOT-1`) is the
right depth for this work-item tier. A deeper decomposition (per-EARS-ID
leaf files) would fragment the contract without improving readability.
Architecture mirrors this with five leaves (A01–A05).

### D8 — Migration is out of scope; target state only

**Directive (2026-04-14):** User directed that migration is out of scope. CLAUDE.md states "No backwards compatibility needed — completely change the schema to get it right." Specific consequences:

- No dual-read fallback. `meridian.toml` is the only project config location; `.meridian/config.toml` is not read.
- No `config migrate` command.
- No Phase A/B/C staged deprecation. There is one release that introduces the new location, breaking any legacy `.meridian/config.toml` without warning.
- `design/spec/migration.md` and `design/architecture/migration-flow.md` are deleted from the package.
- F17, F18, and F19 findings are marked obsolete per this decision.

### D9 — Architect independent sketch consumed and deleted

The independent architecture sketch (`architect-independent-sketch.md`) produced during the design round has been folded into the architecture tree:

- Module enumeration → `design/architecture/paths-layer.md` "Module Layout" section
- Three-layer workspace split (`WorkspaceConfig` / `WorkspaceSnapshot` / `HarnessWorkspaceProjection`) → `design/architecture/workspace-model.md`
- Harness integration refinements and `HarnessWorkspaceSupport` type → `design/architecture/harness-integration.md`
- Shared surfacing builder (`config_surface.py`) → `design/architecture/surfacing-layer.md`
- Four open architectural questions → `design/feasibility.md` "Open Questions"

The sketch file and its prompt (`architect-independent-prompt.md`) were deleted after folding. Future readers should not look for them.

### D10 — Harness-agnostic projection interface

The design extracts `HarnessWorkspaceProjection` as the transport-neutral output
from each harness adapter. Launch composition owns ordered-root planning and
field merging, but it does not branch on mechanism details. This aligns with the
project's core principles:

- Separate policy from mechanism: workspace topology remains policy; adapters own
  how one harness receives that topology.
- Extend, don't modify: adding a harness means one adapter implements one
  projection method rather than editing every launch path.
- Simplest orchestration: the shared layer merges one object instead of growing
  a special-case matrix for `--add-dir` and overlay transports.

**Rejected alternative:** keep an `add_dirs`-centric core and bolt OpenCode onto
it. Smaller delta, wrong abstraction. It would leak harness detail into launch
composition and force future harnesses to pretend they all work like Claude.

### D11 — OpenCode day-1 mechanism is `permission.external_directory`

OpenCode day-1 support uses the native permission surface documented in
`opencode-probe-findings.md §2`, `§4`, and `§5`. Meridian projects enabled
existing workspace roots into a `permission.external_directory` config overlay
and materializes that overlay through `OPENCODE_CONFIG_CONTENT`.

Why this wins:

- Native file tools get direct access to the extra roots.
- The projection interface can represent the mechanism without changing Claude or
  Codex paths.
- The remaining semantic gap is honest and inspectable:
  `active:permission_allowlist`, not fake `active:add_dir` parity.

**Rejected alternative:** MCP filesystem server. It changes the interaction
model for extra roots and adds lifecycle/config complexity with weaker semantic
parity.

**Rejected alternative:** wait for upstream multi-root support. PR #2921 closed
unmerged; no committed timeline exists.

**Rejected alternative:** symlink extra dirs into the project root. Operationally
fragile and hostile to filesystem tooling.

### D12 — Workspace anchor model

**Directive (2026-04-14):** Meridian has a single effective working directory, defined as the parent of the active `.meridian/` directory. All meridian operations (spawn cwd, config discovery, default workspace-file location) anchor to this one directory. Users never see a named "repo root" concept.

**Committed shape:**

1. **Default workspace file location:** `<parent-of-.meridian/>/workspace.local.toml`. Described in docs by relationship to `.meridian/`, not by inventing a "repo root" term.

2. **Explicit override:** `MERIDIAN_WORKSPACE=<path>` points at any file, anywhere on disk. Supports the "workspace outside parent meridian" use case (shared team config, cross-project topologies, test configs) without constraints.

3. **`MERIDIAN_WORKSPACE` path semantics (v1):** absolute paths only. Relative-path resolution is deferred until a concrete user need surfaces. Rationale: the primary use case (workspace outside the meridian tree) wants absolute paths; the relative-path case has no clean universal anchor (shell cwd vs meridian effective cwd both have surprising behaviors).

4. **Paths inside `workspace.local.toml`:** relative to the file itself. Matches VS Code `.code-workspace` convention and every workspace-file tool in the industry. Portable — move the file, paths follow.

5. **Spawn cwd:** parent of `.meridian/` (unchanged behavior). Named as meridian's effective cwd.

**Rejected alternatives:**

- **Named "repo root" user-facing concept.** Implies git coupling that meridian doesn't actually have; overlaps with "parent of `.meridian/`" without adding precision.
- **`MERIDIAN_WORKSPACE` relative paths in v1.** Defers the shell-cwd-vs-meridian-cwd anchor question until a real user asks for relative paths. Absolute paths cover all current use cases.
- **Committed `workspace.toml` layer.** `mars.toml` already plays the "committed team topology" role; adding a second committed file duplicates it.

**Deferred to separate decision:** Walk-up discovery of `.meridian/` (keep walk-up as ergonomic convention, switch to cwd-only, or add visibility instrumentation). This decision is orthogonal to the workspace anchor model — workspace config semantics are the same either way.

**Spec/architecture touchpoints requiring sweep (follow-up pass):**

- `design/spec/workspace-file.md` — replace "repo root" references with relationship to `.meridian/`
- `design/architecture/paths-layer.md` — `ProjectPaths` description; rename `resolve_repo_root` → `resolve_project_root` internally
- `design/feasibility.md` OQ-4 — resolved per (3) above

### D13 — Missing env-target file behavior (OQ-5)

**Directive (2026-04-14):** When `MERIDIAN_WORKSPACE` points at a nonexistent file, meridian treats this as `workspace.status = absent` and emits a per-invocation advisory. The launch proceeds without workspace roots.

**Rationale:** a missing override target is a misconfiguration, not a parse error. Treating it as `invalid` would block legitimate launches when users fat-finger a path. The advisory surfaces the problem without blocking. Matches progressive disclosure.

**Three-way distinction:**

- No env var set → silent `absent` (no workspace file declared)
- Env var set, target missing → `absent` + per-invocation advisory (explicit pointer is broken)
- Env var set, target exists but fails parse → `invalid` (actual contract violation)

**Rejected alternative:** treat missing target as `invalid` and block. Rejected because legitimate launches shouldn't fail because of a workspace-file typo; surfaced diagnostics are the right mechanism.

### D14 — `workspace init --from mars.toml` path emission (OQ-6)

**Directive (2026-04-14):** `workspace init --from mars.toml` emits disabled entries with an **empty path** and the `org/repo` identity as a comment. No path heuristic is applied.

**Rationale:** there is no universal heuristic for "where sibling repos live on disk." This repo's own documented layout (`~/gitrepos/meridian-cli`, `~/gitrepos/prompts/meridian-base`) breaks the obvious `<parent>/../<repo-name>` pattern that the prior round considered. Any heuristic will be wrong for some real layouts.

**Emission shape:**

```toml
# meridian-flow/meridian-base
# [[context-roots]]
# path = ""
# enabled = false

# meridian-flow/meridian-dev-workflow
# [[context-roots]]
# path = ""
# enabled = false
```

The user uncomments and fills in local paths explicitly. Zero chance of wrong paths being parsed as active. Matches the F13 resolution (commented examples only) for the default `workspace init` case — this version just adds package identities from mars.toml as comments.

**Rejected alternative:** `<parent-of-.meridian/>/../<repo-name>` pattern as a default path guess. Rejected because it's factually wrong for this repo's layout and for any non-strict-sibling checkout topology.

**Rejected alternative:** active `enabled = false` entries with guessed paths. Rejected because users may enable them without fixing the path, shipping wrong configs.

### D15 — OpenCode `OPENCODE_CONFIG_CONTENT` collision policy (OQ-1)

**Directive (2026-04-14):** If a parent environment already sets `OPENCODE_CONFIG_CONTENT`, meridian's OpenCode adapter **skips** workspace projection and emits a diagnostic ("workspace projection suppressed — `OPENCODE_CONFIG_CONTENT` already set by parent env"). The user's explicit env value wins.

**Rationale:** silent deep-merging of meridian's workspace overlay into user-supplied JSON is hostile. It modifies user config invisibly, producing surprising behavior that's hard to debug. Skip-with-diagnostic is predictable, makes the suppression visible, and users who want merge semantics can request them as a future opt-in flag.

Implementation is also simpler — no JSON deep-merge logic, no precedence rules between user fields and meridian fields.

**Rejected alternative:** deep-merge meridian's workspace overlay into the existing `OPENCODE_CONFIG_CONTENT` JSON. Rejected because silent modification of user-supplied JSON is the kind of invisible behavior that causes long debug sessions; predictable skip is safer, and merge can be added behind an opt-in flag later if real users ask.

**Rejected alternative:** meridian-precedence overwrite. Rejected because silently dropping the user's env value is worse than refusing to project; the user made an explicit assertion by setting the env.

### D16 — Streaming vs subprocess projection parity (OQ-7)

**Status:** Resolved via code investigation; no architecture change needed.

**Finding:** code inspection of `src/meridian/lib/ops/spawn/execute.py:462` and `src/meridian/lib/harness/connections/opencode_http.py:311-330` confirmed:

1. All three harnesses declare `supports_bidirectional=True`, so `meridian spawn` always routes to `execute_with_streaming` (streaming transport).
2. `execute_with_streaming` still launches the harness binary via `asyncio.create_subprocess_exec(..., env=env)`. "Streaming" refers to the bidirectional IPC mechanism (HTTP/WebSocket), not an absence of subprocess spawning.
3. `env_additions` (including `OPENCODE_CONFIG_CONTENT`) therefore reach the child process identically in both paths.

**Consequence:** `HarnessWorkspaceProjection.env_additions` works uniformly. The OpenCode workspace projection delivers `OPENCODE_CONFIG_CONTENT` through the standard env channel regardless of which runner code path is chosen.

**Related follow-up (out of scope):** issue #32 (`meridian-flow/meridian-cli#32`) filed to remove dead subprocess-runner code (`execute_with_finalization` is unreachable) and clarify the misleading `_subprocess` filenames on shared projection utilities. That cleanup is independent of workspace-config-design.

## How this file is used

- Reviewers: validate that every F1–F19 response is actually encoded in the
  spec/architecture leaves named under "Encoded in" for each row. If a response
  points at a spec/architecture leaf but the leaf does not make the claim, that
  is a convergence gap to flag.
- Planner: use D1–D7 as constraints that survive into the plan. D2 and D3 in
  particular govern phase sequencing.
- Future rounds: when a new prior-round feedback file gets produced, append a
  new section here rather than rewriting these rows.
