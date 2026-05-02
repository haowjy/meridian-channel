# Smoke test: unified dev setup

Purpose: verify the highest-risk user journeys for `meridian chat` frontend serving without duplicating unit or integration coverage.

Run from the `meridian-cli` checkout. These flows assume `../meridian-web` exists and its `node_modules` are installed.

## 1. Raw Vite dev mode (`--no-portless`)

```bash
uv run meridian chat --dev --no-portless --frontend-root ../meridian-web --port 0
```

Expected:

- Process starts the backend and a Vite child process.
- Stdout includes exactly one user-facing dev URL line: `Chat UI (dev): http://127.0.0.1:<vite-port>`.
- The user-facing URL is `http://`, not `https://`.
- No portless banner, portless route, or Tailscale/Funnel messaging appears.
- Process stays up until interrupted.

Then press `Ctrl-C`.

Expected:

- The command exits cleanly.
- Backend shutdown logs appear.

## 2. Portless dev mode when available

Skip this section if `command -v portless` fails.

```bash
uv run meridian chat --dev --frontend-root ../meridian-web --port 0
```

Expected:

- Process starts the backend and launches the frontend through portless.
- Stdout includes exactly one user-facing dev URL line: `Chat UI (dev): https://<stable-host>`.
- The user-facing URL is `https://`, not raw `http://127.0.0.1:<vite-port>`.
- Process stays up until interrupted.

Then press `Ctrl-C`.

Expected:

- The command exits cleanly.
- A second immediate rerun of the same command also starts normally.

## 3. Occupied route failure and `--portless-force`

Skip this section if `portless` is unavailable.

In terminal A, start a normal portless dev session and leave it running:

```bash
uv run meridian chat --dev --frontend-root ../meridian-web --port 0
```

In terminal B, run the same command without force:

```bash
uv run meridian chat --dev --frontend-root ../meridian-web --port 0
```

Expected:

- The second command exits non-zero before serving the UI.
- The error explains that the portless route is occupied.
- The error suggests both:
  - `portless prune`
  - `meridian chat --dev --portless-force`
- The command does **not** silently retry with `--force`.

Still in terminal B, rerun with force:

```bash
uv run meridian chat --dev --portless-force --frontend-root ../meridian-web --port 0
```

Expected:

- The command starts successfully on the initial forced attempt.
- Stdout includes `Chat UI (dev): https://<stable-host>`.

Clean up both terminals with `Ctrl-C` when finished.

## 4. SIGINT cleanup

Start raw dev mode:

```bash
uv run meridian chat --dev --no-portless --frontend-root ../meridian-web --port 0
```

After the dev UI is ready, press `Ctrl-C` once.

Expected:

- The command exits promptly.
- The frontend child does not stay behind as an orphan.
- An immediate rerun of the same command succeeds without needing manual cleanup.

## 5. Headless mode contract

```bash
uv run meridian chat --headless --port 0
```

Expected:

- Stdout prints `Chat backend: http://127.0.0.1:<port>`.
- Stdout does **not** print `Chat UI:` or `Chat UI (dev):`.
- No frontend dev server is started.
- No browser window is opened.
- Process stays up until interrupted.

Optional spot-check for the `--open` contract:

```bash
uv run meridian chat --headless --open --port 0
```

Expected:

- Stdout warns that `--open` is ignored in headless mode.
- The process still behaves as API-only backend startup with no UI served.
