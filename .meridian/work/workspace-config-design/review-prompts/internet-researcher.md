# Prior Art: Workspace/Config Boundaries for Multi-Agent + CLI Tooling

You are feeding external context into a design review for **workspace-config-design** (Meridian's on-disk state model: splitting committed project config out of `.meridian/` into repo-root `meridian.toml`, plus a gitignored `workspace.toml` for local context-root injection into harness launches).

Design summary attached via `-f` (requirements, spec, architecture, decisions). Skim them for context, then answer the research questions below with **concrete, cited findings** — not opinions.

## Research Questions

### RQ1: Directory-inclusion in multi-agent coding tools

Investigate how other agentic/coding CLIs expose "extra context roots" at launch time:

- **Claude Code** (`claude --add-dir`, `settings.json` `additionalDirectories`) — confirm current flag shape and precedence semantics.
- **Codex CLI** (OpenAI) — does it expose a directory-inclusion flag today? `--read-dir`? project-level config for multi-root?
- **OpenCode** — current multi-root/context support.
- **Cursor** — workspace/multi-root directory handling.
- **Cline / Continue** — multi-repo workspace features.
- **Aider** — how it handles auxiliary directories.

For each: name the mechanism, the config file (if any), whether it's project-scoped or user-scoped, and known gotchas. Include links to docs or source.

### RQ2: Monorepo workspace topology file conventions

Investigate the conventions for "topology files" that declare participating roots, to inform `workspace.toml` naming and schema:

- pnpm (`pnpm-workspace.yaml`)
- npm / Yarn workspaces (`package.json` `workspaces` field)
- Rush (`rush.json`)
- Nx (`nx.json`, `workspace.json`)
- Bazel (`WORKSPACE`, `MODULE.bazel`)
- Go (`go.work`)
- Cargo workspaces (`[workspace]` in `Cargo.toml`)
- Bun workspaces
- Deno (`deno.json` workspaces)

For each: file name, location (root vs nested), scope (committed team vs local override), typical contents (paths, patterns, metadata). Are any of them gitignored local-override files, or is Meridian's "local-only workspace" concept unusual?

### RQ3: Config-at-root conventions for CLI tools

Meridian is moving from `.meridian/config.toml` to `meridian.toml` at root. Survey how similar tools converged on their current location:

- Ruff (`ruff.toml`, `pyproject.toml` `[tool.ruff]`)
- Rustfmt (`rustfmt.toml`, `.rustfmt.toml`)
- Biome (`biome.json`)
- ESLint (flat config at root, historical `.eslintrc.*`)
- Prettier (`.prettierrc`, `prettier.config.js`)
- Git (`.gitconfig` user, `.git/config` local)
- Docker (`.dockerconfig`, Compose `compose.yml`)
- `.editorconfig`

Surface: was there a migration like Meridian's proposed one? What migration strategy did they use (advisory, auto-migrate, hard break)? Any regret about where they ended up? What did they do about backward-compat?

### RQ4: Local-override files that are explicitly gitignored

`workspace.toml` is intentionally gitignored. Survey prior art:

- `mars.local.toml` (in-repo, for comparison)
- Cargo's `.cargo/config.toml` local override patterns
- `npm-shrinkwrap.json` vs `package-lock.json` (commit/local distinction)
- `.env` / `.env.local`
- Gradle's `gradle-local.properties`
- Bundler's `.bundle/config`
- VS Code's `.vscode/settings.json` (mixed: sometimes committed, sometimes local)

What naming conventions exist for "local-only" variants? (`.local.`, `.user.`, `-local`, no-prefix-but-gitignored)

### RQ5: `.meridian/` trending fully local — patterns and anti-patterns

Meridian wants `.meridian/` to end up fully local/gitignored, like `.git/`. Survey:

- Tools with dot-dirs that are fully local: `.git/`, `.terraform/`, `.bundle/`, `.venv/`, `node_modules/`.
- Tools with dot-dirs that are partially committed: `.vscode/`, `.idea/`, `.github/`, `.husky/`.
- Cases where a tool migrated from "mixed dot-dir" to "fully local dot-dir + root config" or vice-versa.
- Known pain points with gitignore-exception patterns (`*` + `!file`).

Is there industry guidance on when a tool should use a local-only dot-dir vs split committed config to root?

### RQ6: Harness-agnostic context-root abstractions

Meridian's design exposes `context_directories() → list[Path]` as a harness-agnostic abstraction that each harness adapter consumes. Is this a known pattern elsewhere? Does it usually survive once you add a second consumer, or does it need to be restructured (e.g., tagged per-harness, ordered, scoped)?

### RQ7: Gotchas for the specific change Meridian is making

Surface concrete traps other projects hit when they:
- Moved config from a state directory to repo root.
- Added a gitignored local-override file next to a committed config.
- Introduced a "workspace" / "context-roots" concept late in a product's life.
- Deprecated a gitignore-exception pattern.

## Output Format

Structured report with:

1. **Direct answers to RQ1–RQ7**, each with citations (URLs) or specific code/doc references.
2. **Top 5 insights** the Meridian design team should weigh — ranked by expected impact on v1 shape.
3. **Open risks** the current design does not appear to have considered.
4. **Recommended reframings**, if any, with a concrete alternative sketched.

Keep synthesis sharp. Quotes and links beat generalities.
