# Review: UX, Progressive Disclosure, API Surface

You are reviewing the design package for **workspace-config-design**. Artifacts attached via `-f`.

## Your Focus Area: UX & Surface Area

Other reviewers cover alignment, correctness/migration, refactor structure, and external prior art. Stay in this lane.

## Core Questions

1. **Progressive disclosure.** D9 and WS-1.3 promise single-repo users experience zero new complexity. Walk a first-time single-repo user through `meridian` in a fresh repo post-change:
   - What new files appear at root? (meridian.toml? models.toml? Any others?)
   - What do they see in `git status`?
   - What does `meridian config show` output look like relative to today?
   - Is `workspace.toml` ever referenced in error messages, help text, or `--help`?
   Rate how close to "invisible" the workspace machinery actually is.

2. **Repo-root surface area.** After migration the root has: `meridian.toml`, `models.toml`, `mars.toml`, `mars.lock`, `mars.local.toml`, `workspace.toml`, `pyproject.toml`, `uv.lock`, `.agents/`, `.meridian/`, `.mars/`, `AGENTS.md`. That's a lot. Challenge the design:
   - Does `models.toml` at root pull its weight for typical users? OQ-3 says keep it separate; is that right for discoverability?
   - Do we need both `mars.toml` and `mars.local.toml` and `workspace.toml`? The sync-mars bridge (WS-4.4) implies overlap.
   - Any coherent reframing that reduces files without losing clarity?

3. **Naming.** `[context-roots]` (D6) replaces `[repos]`. Evaluate:
   - Is "context-roots" terminology intuitive? A user who never hears "context roots" elsewhere may not know what it means.
   - Does the term align with Claude's `--add-dir`, Codex's `--read-dir`, and common IDE/editor terminology?
   - Alternatives worth considering: `[extra-dirs]`, `[additional-dirs]`, `[include]`, `[roots]`, `[attach]`.

4. **CLI surface.** Review the proposed commands:
   - `meridian config show` (extended with workspace section) — WS-4.1
   - `meridian config migrate` — CFG-1.3, and OQ-1 recommends it covers models too
   - `meridian doctor` (workspace validation) — WS-4.2
   - `meridian workspace init` — WS-4.3
   - `meridian workspace sync-mars` — WS-4.4
   Are any of these overreach for v1? Any that should exist but don't? Does `workspace init` derived from `mars.toml` dependencies make sense when not all mars deps are local repos?

5. **Error UX.** Architecture §"Error Handling" table:
   - "Fatal with clear message" is hand-wavy — is the intent that a typo in `workspace.toml` crashes every `meridian` invocation including unrelated commands like `meridian spawn ls`? That would be painful. Should workspace failures degrade to a warning for non-spawn commands?
   - What about `meridian.toml` parse errors during migration — does `meridian config migrate` refuse to run, or try to fix?

6. **`config show` ergonomics.** Today `config show` shows resolved operational config. WS-4.1 adds a workspace section. How does a user tell, from one command, (a) which config file is active, (b) whether they're on legacy vs new location, (c) which workspace roots apply, (d) which harnesses skip them? Propose the minimal output that answers all four.

7. **Documentation load.** REF-1 changes AGENTS.md to use `org/repo` + "illustrative paths". This moves setup burden to the developer (they must write `workspace.toml` to get anything working). Is this a net UX improvement or a regression for the first-time contributor?

8. **Non-goal leakage.** Per-harness subsets (non-goal) and settings in workspace (D7/G6) are forbidden. Does the CLI surface accidentally encourage workarounds — e.g., is there any way the user could end up wanting `workspace.toml` to carry a model override, and the current design gives them no guidance on where that belongs?

## Output Format

Use `review` skill structure. Severity + pointer + recommended resolution per finding. Prefer concrete UX rewrites (show output, command shape) over abstract concerns. End with `converged` or `revise`.

Do not edit artifacts.
