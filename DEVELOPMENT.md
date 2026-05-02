# Development

## Setup

```bash
git clone https://github.com/meridian-flow/meridian-cli.git
cd meridian-cli
uv sync --extra dev
```

## Verify

```bash
uv run meridian --version
uv run meridian doctor
```

## Install Validation

Use these when you want to verify the installed CLI behavior, not just `uv run`
from the checkout.

Snapshot install from the current checkout:

```bash
uv tool install --force . --no-cache --reinstall
```

Editable install:

```bash
uv tool install --force --editable . --no-cache --reinstall
```

Then verify the installed tool:

```bash
meridian --version
uv tool list
```

## Test

```bash
uv run pytest-llm
uv run pyright
```

## Release

Use the release helper to bump the package version, create a release commit,
and create the matching `v<version>` tag in one step:

The package version currently lives in `src/meridian/__init__.py` as
`__version__`.

```bash
scripts/release.sh patch
scripts/release.sh 0.1.0 --push
```

By default it updates `src/meridian/__init__.py`, commits the change, and
creates an annotated tag locally. Pass `--push` to push both the current branch
and the new tag.

## Run from source

```bash
uv run meridian --help
```

## Workspace conventions

Workspace config declares sibling directories that harnesses may access during launches.
Commit shared repo-layout conventions in `meridian.toml` with `[workspace.NAME]` entries. Put machine-specific overrides and additions in gitignored `meridian.local.toml`.

If your repos are not at the paths in `meridian.toml`, create `[workspace]` overrides in `meridian.local.toml`:

```toml
[workspace.frontend]
path = "/home/you/src/meridian-web"
```

Missing committed paths are silently skipped so partial checkouts work. Missing local override paths produce `workspace_local_missing_root` because they usually indicate a typo or stale local config. There is no `enabled` field and no subtractive override for disabling an existing committed entry; that limitation is intentional and can be extended later if needed.

See [docs/configuration.md](docs/configuration.md#workspace) for the full schema, projection behavior, and migration details.

## Chat Server + Frontend

The chat backend (`meridian chat`) serves the frontend from built assets by
default. For development with hot reload, use `--dev` mode.

### Quick Start

```bash
# Serve UI from built assets (end user / backend dev path)
make chat

# Dev mode with hot reload (frontend dev path)
make chat-dev
```

### Static mode (default)

`meridian chat` serves pre-built frontend assets alongside the API. No
Node.js required at runtime.

```bash
# Build frontend assets from the sibling meridian-web checkout
make build-frontend

# Serve with built assets
meridian chat --open
```

Asset resolution order:
1. `--frontend-dist <path>` explicit override
2. Packaged assets (from installed wheel)
3. `../meridian-web/dist` convenience fallback

If no assets are found, the server falls back to headless (API-only) mode.

### Dev mode

`meridian chat --dev` starts the backend and a Vite dev server with hot reload:

```bash
meridian chat --dev --open
```

Frontend root resolution:
1. `--frontend-root <path>` explicit flag
2. `MERIDIAN_DEV_FRONTEND_ROOT` env var
3. `../meridian-web` sibling convention

Set `MERIDIAN_ENV=dev` in `.env` for persistent dev mode.

### Portless integration (optional)

When [portless](https://github.com/vercel-labs/portless) is installed, dev
mode uses it automatically for stable HTTPS URLs. Portless is optional — raw
Vite on localhost is the fallback.

```bash
# Install portless (one-time)
npm install -g portless
portless trust

# Dev mode auto-detects portless
meridian chat --dev

# Force raw Vite (skip portless)
meridian chat --dev --no-portless
```

### Network sharing (dev mode only)

Share your dev UI on Tailscale or publicly via Funnel. These require
portless and are always explicit opt-in:

```bash
# Share on your tailnet
meridian chat --dev --tailscale

# Share publicly (requires Funnel ACL)
meridian chat --dev --funnel
```

If a portless route is occupied:
```bash
# Clean up stale routes
portless prune

# Or take over explicitly
meridian chat --dev --portless-force
```

### Headless mode

```bash
meridian chat --headless
# → API-only at http://127.0.0.1:<port>
```
