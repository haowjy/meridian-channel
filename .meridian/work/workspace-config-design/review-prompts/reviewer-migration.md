# Review: Correctness, Migration Safety, Backward Compatibility

You are reviewing the design package for **workspace-config-design** (boundary clarity for Meridian + Mars on-disk state, plus local `workspace.toml`). Artifacts attached via `-f`.

## Your Focus Area: Correctness & Migration

Other reviewers cover framing, UX, refactor structure, and external prior art. Stay in this lane.

## Core Questions

1. **Config resolution correctness.** Spec OWN-1.9/1.10 + architecture `_resolve_project_toml` pseudocode: trace the resolution order against the existing precedence rule (CLI > ENV > YAML profile > project > user > harness default, applied per-field). Does moving from `.meridian/config.toml` to `meridian.toml` preserve that precedence when both files exist, when only one exists, and when neither exists? Is `MERIDIAN_*` env override behavior preserved?

2. **Migration idempotency.** CFG-1.3 says `meridian config migrate` must be idempotent. Walk through:
   - Run once: legacy → root, legacy deleted, gitignore updated.
   - Run again with only root present: no-op, exit clean.
   - Run with a user-modified root file and stale legacy still present (partial prior migration): does the design say what wins?
   - Run with both files divergent (user edited both between versions): what does the design prescribe?
   Flag any of these that are underspecified or would silently destroy user edits.

3. **Two-location fallback lifecycle.** OWN-1.9 keeps `.meridian/config.toml` as fallback indefinitely. OWN-1.10 says root wins + advisory. Is this advisory emitted once per CLI invocation, once per repo (state somewhere), or once per process? Where is the "once" state tracked? Could it become spammy or silent-failing?

4. **Gitignore transitions.** Probe 8 and RF-1 rely on `_DEPRECATED_GITIGNORE_LINES` to strip `!config.toml`. Concerns:
   - Does removing the exception from `.meridian/.gitignore` leave any currently-tracked `config.toml` in git history in an inconsistent state (tracked but now matched by `*`)?
   - If a user runs `meridian` on a repo that has `.meridian/config.toml` still tracked and a fresh `meridian.toml`, what does `git status` look like?
   - `workspace.toml` must land in root `.gitignore` (RF-3, WS-1.2). What if root `.gitignore` doesn't exist? What if user has custom ordering conventions for `.gitignore`?

5. **Models migration parallel.** OWN-1.5 + RF-4 mirror the config migration. Verify the pattern actually applies cleanly. Does `models.toml` have any loader paths that don't go through the central resolver (e.g., `models list` discovery, cache invalidation)? OQ-1 recommends a single `meridian config migrate` for both files — if implemented that way, what's the failure mode if config migrates successfully but models migration fails mid-way?

6. **Workspace injection semantics.** WS-3.3 says dedupe against directories "already present from other sources" (parent settings, passthrough, execution CWD). WS-3.4 says workspace goes BEFORE user passthrough for last-wins. Verify: after dedupe, is last-wins semantics actually preserved? If workspace has `/foo` and passthrough has `/foo`, does dedupe keep the workspace position (violating last-wins intent) or the passthrough position?

7. **Cross-harness silent-skip.** WS-3.5 says harnesses without directory-inclusion mechanisms silently skip. Probe 4 says Codex/OpenCode are no-ops today. If a developer configures `workspace.toml` expecting it to work for Codex, the silence is a footgun. Does `meridian doctor` or `config show` surface which roots apply to which harnesses?

8. **Spawn propagation chain.** Architecture claims workspace propagates through existing parent permission inheritance. Verify: if a top-level Claude spawn gets `--add-dir` from workspace, does its `settings.json` faithfully record those dirs such that `read_parent_claude_permissions` recovers them for the child? Any path-resolution drift (e.g., workspace paths resolved relative to repo root but child runs from a different cwd)?

9. **Env and precedence edge cases.** `MERIDIAN_WORKSPACE` env override (WS-1.4) — does it bypass the repo-root search entirely, or layer on top? If CI sets `MERIDIAN_WORKSPACE` to a file outside the repo, how do relative paths in that file resolve?

## Output Format

Use `review` skill structure. Severity (blocker/major/minor/nit) + pointer + recommended resolution for each finding. End with `converged` or `revise`.

Do not edit artifacts.
