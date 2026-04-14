# Behavioral Specification: Storage Boundaries and Workspace

## Overview

Revised ownership model for on-disk state across Meridian and Mars, with a local workspace concept for centralized context-root injection.

---

## OWN-1: Ownership Model

### Repo Root (Committed Project Policy)

**OWN-1.1** Meridian project config SHALL live at `<repo_root>/meridian.toml`, replacing `.meridian/config.toml` as the primary committed config location.

**OWN-1.2** Mars package manifest SHALL remain at `<repo_root>/mars.toml` with lockfile at `<repo_root>/mars.lock`. No change.

**OWN-1.3** Mars local overrides SHALL remain at `<repo_root>/mars.local.toml`. No change.

**OWN-1.4** The local workspace topology file SHALL live at `<repo_root>/workspace.toml`, gitignored.

**OWN-1.5** Model catalog overrides SHALL move out of `.meridian/models.toml` into a committed repo-root location. The preferred target is `<repo_root>/models.toml` to keep model catalog data separate from `meridian.toml`.

### `.meridian/` (Meridian Runtime and Artifact State)

**OWN-1.6** `.meridian/` SHALL primarily contain runtime/local state: spawn logs, session data, event stores, caches, counters, local workspace state, and other Meridian-owned machine-local files. These are never committed.

**OWN-1.7** `.meridian/fs/`, `.meridian/work/`, and `.meridian/work-archive/` SHALL remain in `.meridian/` for now. They are committed shared artifacts only as a transitional exception because no shared/cloud alternative exists yet.

**OWN-1.8** The long-term contract for `.meridian/` SHALL be fully local/runtime state and fully gitignored. No new committed project config or durable shared state SHALL be introduced under `.meridian/` on the basis of the current `fs/`/`work/` exceptions.

**OWN-1.9** `.meridian/config.toml` SHALL continue to be loaded as a fallback when `meridian.toml` at repo root does not exist, providing backward compatibility during migration.

**OWN-1.10** When both `meridian.toml` (repo root) and `.meridian/config.toml` exist, `meridian.toml` SHALL take precedence. Meridian SHALL emit a one-time advisory suggesting migration.

### `.mars/` (Mars Local State)

**OWN-1.11** Mars local runtime state (sync cache, integrity hashes, etc.) SHALL live under `.mars/` when Mars needs such a directory. Meridian does not create or manage `.mars/`.

**OWN-1.12** `.mars/` SHALL be gitignored.

### `.agents/` (Generated Output)

**OWN-1.13** `.agents/` remains generated output from `mars sync`. No ownership change.

---

## CFG-1: Committed Config Migration

**CFG-1.1** `meridian.toml` SHALL use the same TOML schema as the current `.meridian/config.toml`. No schema changes for migration.

**CFG-1.2** `meridian config show` SHALL indicate which config file is active and its location.

**CFG-1.3** Meridian SHALL provide a `meridian config migrate` command that copies `.meridian/config.toml` to `meridian.toml` and removes the old file. The command SHALL be idempotent.

**CFG-1.4** The `.meridian/.gitignore` SHALL stop tracking `config.toml` once `meridian.toml` exists at repo root. The `!config.toml` exception SHALL be removed from the required gitignore lines.

**CFG-1.5** New projects (first `meridian` invocation in a repo without existing config) SHALL create `meridian.toml` at repo root, not `.meridian/config.toml`.

---

## WS-1: Workspace File Discovery

**WS-1.1** When Meridian starts, it SHALL look for `workspace.toml` at the repo root.

**WS-1.2** `workspace.toml` SHALL be gitignored. Meridian SHALL ensure it is listed in `<repo_root>/.gitignore`.

**WS-1.3** When no `workspace.toml` exists, all workspace features SHALL be completely inert — no warnings, no output, no behavior change.

**WS-1.4** `MERIDIAN_WORKSPACE` environment variable SHALL override the default workspace file location.

---

## WS-2: Workspace File Schema

**WS-2.1** `workspace.toml` SHALL be TOML format.

**WS-2.2** `workspace.toml` SHALL support a `[context-roots]` table where each entry declares a directory to inject into harness launches.

**WS-2.3** Each entry under `[context-roots]` SHALL have a `path` field pointing to the local directory. Paths SHALL support absolute, `~`-relative, and workspace-file-relative formats.

**WS-2.4** `[context-roots]` entries MAY use `org/repo` canonical identifiers as keys for repos, or arbitrary descriptive keys for non-repo directories.

**WS-2.5** Each entry MAY have an `enabled = true|false` flag (default: `true`) to temporarily disable injection without removing the entry.

**WS-2.6** Unknown keys at any level SHALL be preserved and logged at debug level, not treated as errors.

**WS-2.7** `workspace.toml` SHALL NOT contain operational settings (model, harness, approval, timeout, etc.). Those belong in `meridian.toml` or `config.toml`.

---

## WS-3: Context-Root Injection

**WS-3.1** When spawning any harness, Meridian SHALL inject each enabled context-root as an additional directory using the harness-appropriate mechanism:
  - Claude: `--add-dir <path>`
  - Codex: equivalent mechanism if/when available
  - OpenCode: equivalent mechanism if/when available

**WS-3.2** Context-root paths that do not exist on disk SHALL be skipped with a warning.

**WS-3.3** Context-root injection SHALL deduplicate against directories already present from other sources (parent settings inheritance, passthrough args, execution CWD).

**WS-3.4** Workspace-derived directories SHALL be injected BEFORE user passthrough directories so user flags win by last-wins semantics.

**WS-3.5** Context-root injection SHALL apply to all harness types by default. When a harness has no directory-inclusion mechanism, the roots are silently skipped for that harness.

**WS-3.6** Context-roots SHALL propagate to child spawns through the existing parent permission inheritance chain.

---

## WS-4: CLI Surface

**WS-4.1** `meridian config show` SHALL include a `workspace` section showing resolved context-roots when `workspace.toml` is active.

**WS-4.2** `meridian doctor` SHALL validate workspace config: check path existence, warn on disabled entries.

**WS-4.3** Meridian SHALL provide `meridian workspace init` that generates a starter `workspace.toml` pre-populated with entries derived from `mars.toml` dependencies.

**WS-4.4** Meridian SHALL provide `meridian workspace sync-mars` that updates `mars.local.toml` overrides from workspace context-root paths matching `mars.toml` dependencies.

---

## REF-1: AGENTS.md Repo References

**REF-1.1** AGENTS.md SHALL reference repos using canonical `org/repo` identifiers, not filesystem paths.

**REF-1.2** AGENTS.md MAY include a human-readable "preferred local layout" section as documentation, but filesystem paths in that section SHALL be marked as illustrative, not authoritative.

---

## FUT-1: Future Evolution Markers

These statements document design intent without requiring implementation:

**FUT-1.1** The design SHALL NOT create dependencies that prevent migrating `fs/`, `work/`, and `work-archive/` from `.meridian/` to cloud-backed storage, after which `.meridian/` can become fully local/runtime state.

**FUT-1.2** The design SHALL NOT prevent future addition of per-harness context-root subsets in `workspace.toml`.

**FUT-1.3** The design SHALL NOT prevent future addition of a shareable (committed) team workspace concept alongside the local workspace.
