# Feasibility Record

Probe evidence and assumption verdicts for the workspace-config design round. Every claim is cited to a live code line in the `meridian-cli` checkout or to a `codex-cli 0.120.0` help-output capture. This document is ground truth for the spec and architecture trees; `decisions.md` maps prior-round findings to design responses; `design/refactors.md` consumes the blast-radius list below to build the refactor agenda.

> Detailed source captures live in `$MERIDIAN_WORK_DIR/probe-evidence/probes.md`. This file records the verdicts distilled from those probes so the planner and reviewers don't need to re-run them.

## Verdicts

### FV-1 Codex supports `--add-dir`

**Verdict**: feasible. v1 injects workspace roots into claude and codex.

**Evidence**: `codex exec --help` on codex-cli 0.120.0 documents `--add-dir <DIR>` as "Additional directories that should be writable alongside the primary workspace" (see `probes.md §1`).

**Residual risk**: `--add-dir` is inert when the effective sandbox is `read-only`. Codex emits a runtime warning but `config show` / `doctor` must also surface this applicability so users don't reason from assumed behavior. Captured in `architecture/harness-integration.md` and spec `SURF-1.*` leaves on surfacing.

### FV-2 `dedupe_nonempty` is first-seen, and ordering of workspace projection is deterministic

**Verdict**: confirmed. Design commits to the ordering
`user passthrough → projection-managed → workspace-emitted` on the Claude path,
and `user passthrough (spec.extra_args) → workspace-emitted` on the Codex path.

**Evidence**: `lib/launch/text_utils.py:8-19`; `lib/harness/claude_preflight.py:131-147`; `lib/harness/projections/project_codex_subprocess.py:219`. See `probes.md §2`, `§5`, `§6`.

**Residual risk**: none. The design fixes prior F4 by putting user passthrough first so any downstream first-seen dedupe preserves explicit CLI intent.

### FV-3 Meridian does not read `models.toml`; no Meridian-side models migration is justified

**Verdict**: out of scope. `rg "models\.toml|models_merged"` returns zero hits in `src/` and `tests/`. Mars owns alias resolution via `.mars/models-merged.json` (`lib/catalog/model_aliases.py:229`). The design does not propose a Meridian-owned `models.toml` and does not touch mars-agents.

**Evidence**: `probes.md §3`.

**Residual risk**: none. If a future change introduces Meridian-side model ownership, that is a separate decision with separate ownership analysis.

### FV-4 Moving committed config to the project root has a fully enumerated blast radius

**Verdict**: feasible, but the refactor agenda MUST cover all call sites. Any "one-function change" framing is rejected.

**Evidence**: `probes.md §4` enumerates ≥ 9 source sites + help text + smoke + unit tests:

- `lib/state/paths.py:21, 33, 127` — canonical path, gitignore policy.
- `lib/config/settings.py:25, 206-210, 213-227` — loader resolver + user-config env.
- `lib/ops/config.py:342-343, 602-606, 737-763, 758, 777, 827, 846, 872` — command family + bootstrap.
- `lib/ops/manifest.py:242, 266` — CLI help.
- `cli/main.py:806-815` — config_app description.
- `tests/smoke/quick-sanity.md:45-47`, `tests/ops/test_runtime_bootstrap.py`, `tests/ops/test_config_warnings.py`, `tests/config/test_settings.py`, `tests/test_state/test_paths.py`, `tests/cli/test_sync_cmd.py`, `tests/test_cli_bootstrap.py` — tests.

**Residual risk**: the command family (`config show/get/set/reset/init`) currently bypasses `_resolve_project_toml` and operates directly on `_config_path`. A partial refactor that rewires only the loader would leave reads resolving from the new location while writes still target `.meridian/config.toml`. `design/refactors.md` pins this as a single coordinated refactor (R02), not two.

### FV-5 `StatePaths` is `.meridian`-scoped and is the wrong home for project-root file policy

**Verdict**: new module required. Root-file discovery, `MERIDIAN_WORKSPACE` env handling, and root `.gitignore` policy live outside `state/paths.py`.

**Evidence**: `lib/state/paths.py:93-128`, `lib/config/settings.py:789-823` (only `resolve_repo_root` exists at project-root level today; no file enumeration (this will be renamed to `resolve_project_root` per R01)). See `probes.md §7`.

**Residual risk**: naming bikeshed (`ProjectPaths` vs `RepoFiles` vs `RootConfigPaths`). The architecture tree commits to one name; no functional implication.

### FV-6 First-run auto-bootstrap currently creates `.meridian/config.toml` unconditionally; root-file creation must be opt-in

**Verdict**: the bootstrap path must be split. `.meridian/` state directories and `.meridian/.gitignore` continue to be created on every run (runtime state is always needed). Root `meridian.toml` is created ONLY by `config init`.

**Evidence**: `lib/ops/config.py:737-763` — `ensure_state_bootstrap_sync` auto-writes `_scaffold_template()` if the config file is missing; called unconditionally from `lib/ops/runtime.py:66`. See `probes.md §8`.

**Residual risk**: when no `meridian.toml` exists at the project root, the loader runs on built-in defaults silently. `config init` is the user's entrypoint to opt into a committed project config. Stale `.meridian/config.toml` files in existing repos are ignored — the file is no longer read and is deleted by `R01` as part of the boundary cleanup.

### FV-7 Claude already has a projection-managed middle section; workspace projection extends it

**Verdict**: feasible. Claude's existing preflight-owned `execution_cwd` and
parent-forwarded `additionalDirectories` become the projection-managed middle
section, and workspace roots append after them.

**Evidence**: `lib/harness/claude_preflight.py:131-147`. See `probes.md §6`.

**Residual risk**: interaction with parent-forwarding edge cases (no parent `.claude/settings.json`, symlink to parent session dir). Existing behavior unchanged.

### FV-8 — (obsolete) config migrate policy

Removed per D8 (no migration).

### FV-9 OpenCode has day-1 workspace support through `permission.external_directory`

**Verdict**: feasible. OpenCode does not expose native `--add-dir` parity, but
it does expose `permission.external_directory` in its config schema plus inline
config delivery via `OPENCODE_CONFIG_CONTENT`. Day-1 support is therefore a
projection to `active:permission_allowlist`, not an unsupported state.

**Evidence**:

- `.meridian/work/workspace-config-design/opencode-probe-findings.md §1-§2` —
  no first-class multi-root field or agent roots field was found.
- `.meridian/work/workspace-config-design/opencode-probe-findings.md §4` —
  `permission.external_directory` is the documented native permission mechanism
  for paths outside the primary root.
- `.meridian/work/workspace-config-design/opencode-probe-findings.md §8` —
  recommendation is day-1 support via native file-tool access, not a wait-for-upstream posture.

**Residual risk**: semantic gap, not capability gap. The extra roots are usable by
OpenCode's file tools, but they are not surfaced as named workspace roots in the
harness UX. The architecture captures this as
`active:permission_allowlist` rather than pretending OpenCode gained `--add-dir`
parity.

### FV-10 OpenCode config overlay can be delivered through `OPENCODE_CONFIG_CONTENT`

**Verdict**: feasible. The OpenCode projection can keep a structured
`config_overlay` and materialize it into `env_additions` without adding a
launch-layer branch.

**Evidence**:

- `.meridian/work/workspace-config-design/opencode-probe-findings.md §5` —
  `OPENCODE_CONFIG_CONTENT` exists as an inline config env mechanism.
- `.meridian/work/workspace-config-design/opencode-probe-findings.md §2` —
  config schema includes the relevant permission surface.
- `.meridian/work/workspace-config-design/opencode-probe-findings.md §4` —
  config layering is already how OpenCode accepts non-CLI capability changes.

**Residual risk**: explicit merge semantics remain to be pinned if a parent
environment already supplies `OPENCODE_CONFIG_CONTENT`. The architecture records
that as an open question instead of hiding it.

## Open Questions

1. **OpenCode overlay collision policy.** Resolved per D15. If a parent
   environment already sets `OPENCODE_CONFIG_CONTENT`, meridian's OpenCode
   adapter skips workspace projection and emits a diagnostic. The user's
   explicit env value wins. Silent deep-merge rejected as hostile
   invisible-modification behavior.

2. **`[context-roots]` vs `[extra-dirs]` table naming (prior F16).**
   **Status:** deferred. Low priority; architecture commits to `[context-roots]`
   for consistency with Meridian's existing "context" language
   (`MERIDIAN_CHAT_ID`, "context handoffs"). If a reviewer prefers
   `[extra-dirs]`, trivial rename.

3. **`workspace.local.toml` rename rationale (prior F15).** Accepted. The
   architecture uses `workspace.local.toml` explicitly; decisions.md records the
   rationale (pnpm/npm/Yarn/Rush/Nx/Bazel/Go/Cargo/Bun/Deno all treat
   `workspace.*` as committed team topology; a gitignored `workspace.toml` lies
   to the reader).

4. **`MERIDIAN_WORKSPACE` path resolution semantics.** Resolved per D12.
   V1 supports absolute paths only. Per D18, non-absolute override values are
   treated as broken explicit overrides: workspace topology becomes absent for
   that invocation, an advisory is surfaced, and Meridian does not fall through
   to default discovery. Paths *inside* `workspace.local.toml` are resolved
   relative to the file itself, matching VS Code `.code-workspace` convention.

5. **Missing env-target file behavior.** Resolved per D13. `workspace.status
   = absent` + per-invocation advisory when `MERIDIAN_WORKSPACE` points at a
   nonexistent file. Distinguishes from silent `absent` (no env var set),
   `override_non_absolute` (broken non-absolute override), and `invalid`
   (parse/schema error on an existing file). Launch proceeds without workspace
   roots; advisory surfaces the misconfiguration without blocking.

6. **`workspace init --from mars.toml` path heuristic.** Resolved per D14.
   No path heuristic is applied. Emission shape is disabled entries with an
   empty `path` and the `org/repo` identity as a comment. User fills in local
   paths explicitly. Rejected `<parent-of-.meridian/>/../<repo-name>` pattern
   because it is wrong for this repo's own documented layout
   (`~/gitrepos/meridian-cli` + `~/gitrepos/prompts/meridian-base`) and any
   non-strict-sibling checkout topology.

7. **OpenCode subprocess/streaming parity.** Resolved per D16 via code
   investigation. Both paths ultimately call `asyncio.create_subprocess_exec`
   with an `env` param (see `src/meridian/lib/harness/connections/opencode_http.py:311-330`
   and `src/meridian/lib/ops/spawn/execute.py:462`). `env_additions` — including
   `OPENCODE_CONFIG_CONTENT` — flow identically to the child process in both
   modes. No architecture change needed; the projection `env_additions` channel
   works uniformly. A separate cleanup issue (meridian-flow/meridian-cli#32)
   tracks removing the unreachable subprocess-runner code.

## How this file was produced

Probes re-run on 2026-04-14 against `meridian-cli` HEAD and `codex-cli 0.120.0`. Full capture in `$MERIDIAN_WORK_DIR/probe-evidence/probes.md`. Verdicts above are distilled from that capture. When reviewers rerun probes, probes.md is the starting point; if any probe changes behavior, update this file's verdicts first, then propagate to spec/architecture/refactors.
