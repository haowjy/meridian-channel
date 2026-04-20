# Server Lifecycle

## One Server Per Project Root

`meridian app` is project-scoped.

- Start command from a project directory.
- Server root is that directory.
- UI served at `http://localhost:7676`.
- Sessions and spawns shown by that server belong to that project only.

This is the Jupyter model: launch in a directory, browse that directory.

## State Files

### Project-Level Lockfile: `<project_root>/.meridian/app/server.json`

Written atomically on server start, deleted on clean shutdown. Contains what is needed to reconnect or validate the running server for this project.

```json
{
  "pid": 12345,
  "port": 7676,
  "host": "127.0.0.1",
  "project_root": "/home/user/meridian-cli",
  "started_at": "2026-04-19T14:30:00Z"
}
```

No global app registry and no root add/remove state.

## Startup Flow (`meridian app`)

Startup is serialized under `<project_root>/.meridian/app/server.flock` so concurrent starts in the same project do not race.

```text
0. Resolve current working directory as project_root
1. Ensure <project_root>/.meridian/app/ exists
2. Acquire flock on <project_root>/.meridian/app/server.flock
3. Read <project_root>/.meridian/app/server.json
   - If PID alive: open existing project server and exit
   - If PID dead: delete stale lockfile and continue
4. Bind listening socket (default 127.0.0.1:7676)
5. Write <project_root>/.meridian/app/server.json
6. Release startup flock
7. Start uvicorn using the pre-bound socket
8. Open browser unless --no-browser
```

If flock acquisition times out, print an error suggesting another `meridian app` is starting for this project and exit.

### Stale Server Detection

A lockfile is stale if and only if the PID is dead (`os.kill(pid, 0)` raises `ProcessLookupError`).

### Port Selection

Default port is `7676`. If the port is already in use by another process, startup fails with a clear message:

- show conflicting address (`127.0.0.1:7676`)
- recommend `meridian app stop` in the owning project or `--port <n>`

## Shutdown Flow

### Clean Shutdown

```text
1. uvicorn receives signal
2. FastAPI lifespan shutdown begins
3. Set draining flag — reject new POST /api/spawns
4. Wait for in-flight spawn-creation requests to finish (10s safety timeout)
5. SpawnManager.shutdown() stops active harness connections
6. Delete <project_root>/.meridian/app/server.json
7. Exit
```

### Crash

If process is killed, lockfile remains. Next startup in the same project detects dead PID, deletes stale file, and proceeds.

## Server Discovery (`meridian app list`)

Discovery is project-local:

```text
1. Resolve current working directory as project_root
2. Read <project_root>/.meridian/app/server.json
3. If missing: "No server running for this project"
4. If PID dead: delete stale file, "No server running for this project"
5. If PID alive: optionally probe /api/health and print status
```

## Server Stop (`meridian app stop`)

Stops the server for the current project root.

```text
1. Resolve current working directory as project_root
2. Read <project_root>/.meridian/app/server.json
3. If missing or stale: report no server running
4. Send SIGTERM
5. Wait up to 5s
6. If still alive: SIGKILL
7. Clean up lockfile if still present
```

## Health Endpoint

`GET /api/health` returns server identity and status:

```json
{
  "status": "ok",
  "port": 7676,
  "host": "127.0.0.1",
  "pid": 12345,
  "project_root": "/home/user/meridian-cli",
  "active_sessions": 5,
  "active_spawns": 3,
  "uptime_secs": 123.4
}
```

## Edge Cases

**Two terminals run `meridian app` in the same project.**
Startup flock serializes them. First process writes lockfile; second process opens existing server.

**User starts `meridian app` in project A and then in project B on default port.**
Project B fails to bind `127.0.0.1:7676` and prints conflict guidance. This is expected; one port cannot host two project servers.

**Server crashes while spawns are running.**
Spawn state is already persisted under `<project_root>/.meridian/`. Next startup in that project restores visibility from persisted state.

**User deletes `<project_root>/.meridian/app/` while server is running.**
Server keeps running in memory. A later `meridian app` may start a second process because lockfile is gone. This is user-induced state corruption and does not need special recovery logic.

**Project directory moved or deleted while server is running.**
Health endpoint should flip to degraded and file APIs should return project-unavailable errors.

## File Layout

```text
<project_root>/
  .meridian/
    app/
      server.json           # Project-scoped server lockfile
      server.flock          # Startup serialization flock
      sessions.jsonl        # Session registry for this project
    spawns.jsonl            # Project-scoped spawn store
    spawns.jsonl.flock      # Spawn-store lock
    spawns/
      <spawn_id>/
        output.jsonl
        inbound.jsonl
        control.sock
        harness.pid
        heartbeat
        report.md
        home/
        config/
```

The `.meridian/app/` directory is created on first `meridian app` invocation in a project.

---

---

## Access Modes

Jupyter-like access model. Default is local-only; token auth auto-enabled for any non-localhost binding.

### Local (default)

```bash
meridian app
# Binds to 127.0.0.1:7676
# Opens chrome --app=http://localhost:7676
# No auth required — localhost trusted
```

### LAN Access

```bash
meridian app --host 0.0.0.0
# Binds to all interfaces
# Token auth auto-enabled
# Prints: http://192.168.1.x:7676?token=<generated>
```

### Remote (Tunnel)

```bash
meridian app --tunnel
# Starts cloudflared tunnel
# Token auth auto-enabled
# Prints: https://abc123.trycloudflare.com?token=<generated>
```

### SSH Forward (manual)

```bash
# User handles this themselves — stays localhost, no token needed
ssh -L 7676:localhost:7676 user@server
```

---

## Security Model

| Mode | Binding | Auth | HTTPS |
|------|---------|------|-------|
| Local | 127.0.0.1 | None | No |
| LAN | 0.0.0.0 | **Auto-enabled** | No (optional) |
| Tunnel | 127.0.0.1 + tunnel | **Auto-enabled** | Yes (tunnel provides) |

**Rule: If `host != 127.0.0.1` or `tunnel = true`, token auth is required. No opt-out.**

To explicitly disable (unsafe, not recommended):
```bash
meridian app --host 0.0.0.0 --no-token  # prints warning
```

### Token Auth

```python
# Generated on first run, persisted
token = secrets.token_urlsafe(32)
save_to("~/.meridian/app-token")

# Auto-enabled when exposing outside localhost
def requires_token(config) -> bool:
    return config.host != "127.0.0.1" or config.tunnel

# Validated on every request (when enabled)
@app.middleware("http")
async def check_token(request, call_next):
    if requires_token(config):
        if request.query_params.get("token") != stored_token:
            if request.cookies.get("meridian-token") != stored_token:
                return Response("Unauthorized", status_code=401)
    return await call_next(request)
```

Token passed via:
1. Query param: `?token=xxx` (initial access, sets cookie)
2. Cookie: `meridian-token` (subsequent requests)

### Config

```toml
# meridian.toml or ~/.meridian/config.toml
[app]
host = "127.0.0.1"      # "0.0.0.0" for LAN
port = 7676
tunnel = false          # auto-start cloudflare tunnel
# token auth auto-enabled when host != localhost or tunnel = true
```

---

## CLI

```bash
meridian app                     # Local, no auth
meridian app --host 0.0.0.0      # LAN, token auth (automatic)
meridian app --tunnel            # Remote, token auth (automatic)
meridian app --port 8080         # Custom port
meridian app --no-open           # Don't open browser
meridian app token               # Print current token
meridian app token --reset       # Generate new token
```

---

## QR Code Access

When running with network access, display a QR code for easy mobile/device access.

### Terminal Output

```
$ meridian app --host 0.0.0.0

  ┌────────────────────────────────────────┐
  │  Meridian running on port 7676         │
  │                                        │
  │  Local:   http://localhost:7676        │
  │  Network: http://192.168.1.42:7676     │
  │                                        │
  │  Scan to connect:                      │
  │                                        │
  │    █████████████████████████████       │
  │    █████████████████████████████       │
  │    ████ ▄▄▄▄▄ █ ▄██▀█ ▄▄▄▄▄ ████       │
  │    ████ █   █ █▀█ ▀█ █   █ ████       │
  │    ████ █▄▄▄█ █▀▄▀▄█ █▄▄▄█ ████       │
  │    █████████████████████████████       │
  │    █████████████████████████████       │
  │                                        │
  │  Token: abc123...  (copied to clipboard)│
  └────────────────────────────────────────┘

Press Ctrl+C to stop
```

### QR Code Contains

Full URL with token embedded:
```
http://192.168.1.42:7676?token=<full-token>
```

Scanning → opens browser → cookie set automatically → no typing required.

### Implementation

```python
# pip install qrcode[pil] — or use segno (pure python, no PIL)
import qrcode

def print_qr_access(host: str, port: int, token: str):
    url = f"http://{host}:{port}?token={token}"
    
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.print_ascii(invert=True)  # Terminal-friendly
    
    # Also copy token to clipboard if available
    try:
        import pyperclip
        pyperclip.copy(token)
        print(f"Token copied to clipboard")
    except ImportError:
        print(f"Token: {token}")
```

### When to Show QR

| Mode | QR Code |
|------|---------|
| Local (`127.0.0.1`) | No — not useful |
| LAN (`0.0.0.0`) | **Yes** |
| Tunnel | **Yes** — shows tunnel URL |

### In-App QR

Also accessible from the UI for sharing:

```
Settings → Share Access → [QR Code] [Copy Link]
```

Useful when terminal is no longer visible.
