# Decisions

## D1: TOML Format for All Config (Preserved)

**Decision**: Use TOML for `meridian.toml` and `workspace.toml`.

**Reasoning**: Every Meridian/Mars config file is TOML. Consistency reduces cognitive load. Python stdlib `tomllib` handles reading.

**Alternatives rejected**:
- **JSON**: Lacks comments, essential for hand-edited config.
- **YAML**: Meridian has no YAML config files. Indentation sensitivity is poor for agent-edited files.

---

## D2: Committed Config at Repo Root (Revised from Prior D2)

**Decision**: Move committed project config from `.meridian/config.toml` to `<repo_root>/meridian.toml`.

**Reasoning**: The prior design (D2) placed `workspace.toml` at root but left `config.toml` in `.meridian/`. The corrected framing recognizes that committed project policy should live at root — this is the more fundamental boundary problem. `.meridian/` should mean runtime state, not committed config behind gitignore exceptions.

Moving config to root:
- Follows the `<tool>.toml` convention (`mars.toml`, `pyproject.toml`, `ruff.toml`).
- Makes project config discoverable via `ls`.
- Simplifies `.meridian/.gitignore` by removing tracked exceptions.
- Creates a consistent repo-root layer: `meridian.toml` (config) + `mars.toml` (packages) + `workspace.toml` (topology).

**What changed from prior design**: Prior design only addressed workspace file placement. This revision addresses the broader boundary problem — committed config belongs at root, and workspace is just one file in that layer.

**Alternatives rejected**:
- **Keep `.meridian/config.toml`**: Perpetuates the gitignore-exception pattern. Not discoverable. Conflates committed policy with runtime state.
- **Merge into `pyproject.toml` under `[tool.meridian]`**: Technically possible but couples Meridian config to Python packaging conventions. Non-Python repos using Meridian would need a `pyproject.toml` just for config.

---

## D3: `org/repo` as Canonical Identifier (Preserved)

**Decision**: Use `org/repo` format for canonical repo references.

**Reasoning**: Stable identity from hosting platform. Already in mars.toml URLs. Globally unambiguous. Readable.

**Alternatives rejected**: mars dependency name (local alias, not stable), full URL (too verbose), short name (ambiguous).

---

## D4: Workspace Orthogonal to Config Precedence (Preserved)

**Decision**: Workspace config is orthogonal to MeridianConfig precedence. It provides topology, not operational config.

**Reasoning**: Config precedence resolves operational parameters (model, harness, approval). Workspace answers "which directories participate in my environment?" — a different concern.

**Alternatives rejected**: Workspace as precedence layer — would conflate topology with operational overrides.

---

## D5: Mars Remains Conceptually Separate (Expanded)

**Decision**: Mars-owned state and config never live under `.meridian/`. Meridian-owned state and config never live under `.mars/`. Mars.local.toml is bridged, not replaced.

**Reasoning**: Meridian and Mars are intertwined products but should remain separable. Mars may be used without Meridian. Coupling Mars local state to Meridian's state root creates an unnecessary dependency.

**What changed**: Prior D5 focused only on `mars.local.toml` not being replaced. This revision explicitly establishes the bidirectional boundary: neither product stores state in the other's directory.

---

## D6: `[context-roots]` Not `[repos]` (Revised from Prior D6)

**Decision**: Workspace file uses `[context-roots]` table, not `[repos]`.

**Reasoning**: The prior design used `[repos]` and `add-to-context` flag. But the actual use case is injecting directories into harness context — not all of which are git repos. A shared data directory, a monorepo subtree, or a documentation checkout should work identically. `[context-roots]` names the concept accurately: these are additional context roots for harness launches. The `add-to-context` flag becomes `enabled` since the primary (only) purpose of listing a root is context injection.

**What changed**: Prior design conflated "repo declaration" with "context injection." This revision recognizes that context-root injection IS the workspace concept — declaring repos is just one use case.

**Alternatives rejected**:
- `[repos]` with `add-to-context`: Names the container wrong. Not all entries are repos.
- `[directories]`: Too generic. Doesn't convey the harness-injection semantics.

---

## D7: No `[settings]` Table in Workspace (New)

**Decision**: `workspace.toml` has no `[settings]` table. It is purely topology.

**Reasoning**: The prior design included `[settings]` as a reserved extension point. The corrected framing (requirement G6) explicitly separates settings/config from workspace/topology. Operational settings belong in `meridian.toml`. Adding a settings table to workspace creates a parallel config surface that competes with `meridian.toml` and invites scope creep.

**Constraint**: If a future need arises for per-workspace operational overrides, evaluate extending `meridian.toml` with a local overlay mechanism, not adding settings to `workspace.toml`.

**Alternatives rejected**:
- `[settings]` as extension point: Violates separation of concerns. Makes workspace a junk drawer.

---

## D8: models.toml Stays Separate (New)

**Decision**: Keep `models.toml` as a separate file (moved to repo root), not merged into `meridian.toml`.

**Reasoning**: The model catalog schema (`[aliases]`, `[metadata.*]`, `[harness_patterns]`, `[model_visibility]`) is self-contained and orthogonal to operational config. Merging would create a `[models.aliases]`, `[models.harness_patterns]` etc. nesting that adds visual noise without semantic benefit. Two focused files are clearer than one cluttered file.

**Alternatives rejected**:
- **Merge into `meridian.toml`**: Awkward nesting. The schemas are distinct and independently useful.

---

## D9: Workspace Features Completely Inert Without Config (Preserved)

**Decision**: No `workspace.toml` → zero workspace behavior. No warnings, no prompts, no output.

**Reasoning**: Most users work in single repos. They should never encounter workspace complexity. Progressive disclosure: the feature exists for those who need it and is invisible to those who don't.

---

## D10: Backward-Compatible Config Migration (New)

**Decision**: `.meridian/config.toml` continues to work as a fallback. Migration is opt-in via `meridian config migrate`.

**Reasoning**: Breaking existing users' config on upgrade is unacceptable. The fallback ensures existing repos work unchanged. The migration command makes the transition explicit and idempotent. New repos get the new location by default.

**Alternatives rejected**:
- **Auto-migrate on first run**: Destructive without consent. Config file moves are visible in git status and may confuse developers.
- **Support both locations indefinitely**: Creates long-term confusion about which location is canonical. Advisory nudges developers toward migration without forcing it.

---

## D11: Prior Workspace-Only Design Superseded (New)

**Decision**: The prior design package (focused solely on `workspace.toml`) is superseded by this revised package.

**Reasoning**: The prior design correctly identified the workspace use case but framed it as the primary problem. The real problem is boundary clarity across the entire on-disk state model. Workspace is one component of the solution, not the solution. The revised design addresses config location, state ownership, Mars separability, and workspace injection as a cohesive whole.

**What carries forward from prior design**: TOML format, org/repo identifiers, workspace orthogonal to config precedence, mars.local.toml bridging, progressive disclosure, harness injection architecture (all structurally sound). What changes: framing, scope, file naming (`[context-roots]` not `[repos]`), no `[settings]` table, config migration as a core component.

---

## D12: `.meridian/` Fully Local Is the Target Model (New)

**Decision**: Treat `.meridian/` as a directory that trends toward fully local/runtime state and fully gitignored. The currently committed `fs/`, `work/`, and `work-archive/` paths are temporary exceptions until Meridian has a shared/cloud alternative for those artifact classes.

**Reasoning**: The revised design already moved committed config out of `.meridian/`, but the stronger clarification is that this is not just repo cleanup. It establishes the long-term contract for `.meridian/`: local tool state, not shared project policy. Keeping `fs/` and `work/` committed for now is a pragmatic bridge because they currently act as the team's shared persistence layer. That exception should not be misread as permission to add more committed config or durable shared data under `.meridian/`.

This choice keeps the current workflow functioning while preserving a clean future migration path:
- today: `fs/` and `work/` survive through git because no shared backend exists
- later: shared/cloud state replaces them
- end-state: `.meridian/` is fully local/runtime and gitignored

**Alternatives rejected**:
- **Treat committed `fs/`/`work/` as normal permanent `.meridian/` contents**: Locks in the current mixed model and weakens the case for moving committed config to root.
- **Move `fs/`/`work/` immediately**: Premature without a replacement shared persistence layer.
