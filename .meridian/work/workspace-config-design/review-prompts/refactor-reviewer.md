# Refactor Review: Structural Health of the Refactor Agenda

You are reviewing the design package for **workspace-config-design**. Artifacts attached via `-f`, plus `src/meridian/lib/config/settings.py` for grounding.

## Your Focus Area: Structural Rearrangement

Other reviewers cover alignment, correctness/migration, UX, and external prior art. Stay in this lane. Apply the `dev-principles` discipline rigorously:

- **Abstraction threshold:** extract at 3+ genuine instances of the same semantic pattern, not at 2.
- **Deletion courage:** flag code the design preserves that has no clear reason to exist after the change.
- **Greppability / coupling:** flag if the design raises coupling or hides dispatch behind dynamic dispatch.
- **Preparatory refactors first:** refactors sequenced in an order that makes the feature change easy.

## Core Questions

1. **RF-1 scope & sequencing.** "One function change in `settings.py`, update `StatePaths` to include root config path, update `_GITIGNORE_CONTENT` and `_REQUIRED_GITIGNORE_LINES`." Is this actually scoped right, or does moving config location cascade into callers that today assume `.meridian/config.toml` (e.g., `config migrate`, `config show`, health probes in `doctor`, test fixtures)? Enumerate the true blast radius.

2. **RF-2 extraction warranted?** The architecture proposes extracting harness context directory resolution from `claude_preflight.py` because workspace injection would otherwise be hardcoded there. Check:
   - How many distinct callers will use the extracted function at v1? If only `claude_preflight.py` consumes it (Codex/OpenCode are probe-verified as no-op), this is a 1-instance abstraction, not a 3-instance one. Is the extraction premature?
   - Alternative: inline workspace injection into `claude_preflight.py` now, extract when a second harness gains support.
   - If you agree extraction is warranted, is the interface (`context_directories() → list[Path]`) the right shape, or does it leak the assumption of a single flat list when harnesses may eventually need tagged/per-mode injection?

3. **RF-3 utility placement.** `ensure_root_gitignored(repo_root, entry)` — where does this live? `state/paths.py` already owns `.meridian/.gitignore` management. Putting root gitignore logic there couples state-root concerns with repo-root concerns. Is there a more natural home (e.g., a `git_utils.py`)? Is `state/paths.py` already too large / multi-responsibility?

4. **RF-4 parallelism.** Models.toml migration mirrors config migration. Should RF-4 come with an extracted helper that both config and models loaders use (dedup the "check root first, fall back to `.meridian/`" pattern), or is that premature (2 instances = leave duplicated)? If the helper is the right call, is it captured in the agenda?

5. **Missing refactors.** The agenda has 4 entries. Consider whether any of these are missing:
   - `StatePaths` evolution: it probably needs a `root_config_path` and `root_models_path` field. Is that structural enough to warrant its own RF entry?
   - `MeridianConfig` construction: if workspace is loaded lazily at preflight, does the config object still need a reference to workspace, or does the adapter reach into workspace directly? If the latter, `claude_preflight.py` is growing a new dependency without a matching abstraction.
   - `AGENTS.md` edit (REF-1): this is documentation, not a refactor, but is there a pattern for making "canonical identifiers in docs" enforceable (lint, link-check)?
   - `_DEPRECATED_GITIGNORE_LINES` mechanism: Probe 8 refers to it — is that mechanism already proven, or does adding to it constitute a refactor that deserves its own entry?

6. **New module shape: `src/meridian/lib/config/workspace.py`.** Architecture sketches `WorkspaceConfig`, `ContextRoot`, `load_workspace`, `context_directories`. Evaluate:
   - Is the module cohesive? (loading + resolution + validation in one module is fine; any reason to split?)
   - Does it belong under `config/` or under a new top-level (e.g., `workspace/`)? Workspace isn't operational config — is it miscategorized?
   - Pydantic frozen model for 3 fields + 2 free functions — right shape, or does it want a class with methods for `enabled_dirs()` etc.?

7. **Coupling deltas.** Does the design raise coupling anywhere (import lists growing, new cross-module dependencies)? Specifically:
   - `claude_preflight.py` gains a dependency on `config/workspace.py`.
   - `settings.py` potentially gains a dependency on root-gitignore utilities.
   - `doctor` commands gain a dependency on workspace validation.
   Flag any of these that compound poorly.

8. **Structural signals.** `settings.py`, `claude_preflight.py`, `state/paths.py` — run the size/responsibility heuristics from `dev-principles`. Does this change push any of them past the "split candidate" threshold?

## Output Format

Use `review` skill structure. For each finding, severity + pointer + recommended resolution. Prefer concrete "promote this to RF-5 with the following scope" / "RF-2 is premature, inline instead" over vague warnings. End with `converged` or `revise`.

Do not edit artifacts. Read-only review.
