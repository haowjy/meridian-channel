"""CLI command for the meridian app web UI server."""

from __future__ import annotations

import importlib
import json
import logging
import socket
import subprocess
from pathlib import Path

from meridian.lib.platform import IS_WINDOWS

logger = logging.getLogger(__name__)


def _detect_tailscale_origins(port: int) -> list[str]:
    """Try to detect the local Tailscale FQDN and return origin URLs.

    Returns an empty list if Tailscale is not installed or not running.
    """
    try:
        result = subprocess.run(
            ["tailscale", "status", "--self", "--json"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        dns_name: str = data.get("Self", {}).get("DNSName", "")
        if not dns_name:
            return []
        # Tailscale returns FQDN with trailing dot — strip it.
        hostname = dns_name.rstrip(".")
        if not hostname:
            return []
        return [f"http://{hostname}:{port}"]
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []


def run_app(
    uds: str | None = None,
    port: int | None = None,
    host: str = "127.0.0.1",
    proxy: str | None = None,
    debug: bool = False,
    cors_origins: list[str] | None = None,
    tailscale: bool = False,
    allow_unsafe_no_permissions: bool = False,
) -> None:
    """Start the Meridian app server."""

    # Configure logging early so pre-uvicorn messages (e.g. Tailscale
    # detection) are visible. Uvicorn reconfigures on start, so this
    # only covers the startup preamble.
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s:     %(message)s")

    uvicorn_module = importlib.import_module("uvicorn")

    from meridian.lib.app.server import create_app
    from meridian.lib.ops.runtime import resolve_runtime_root, resolve_runtime_root_and_config
    from meridian.lib.state.user_paths import get_or_create_project_uuid
    from meridian.lib.streaming.spawn_manager import SpawnManager

    project_root, _ = resolve_runtime_root_and_config(None)
    runtime_root = resolve_runtime_root(project_root)
    meridian_dir = project_root / ".meridian"
    project_uuid = get_or_create_project_uuid(meridian_dir)

    manager = SpawnManager(runtime_root=runtime_root, project_root=project_root, debug=debug)

    use_tcp = IS_WINDOWS or port is not None or host != "127.0.0.1"
    if use_tcp:
        resolved_port = port if port is not None else 7676

        all_origins = list(cors_origins or [])

        # --tailscale: auto-detect local Tailscale FQDN via `tailscale status`
        # and whitelist it as a CORS + WebSocket origin. This lets you access
        # the app from other devices on your tailnet without manually passing
        # --cors-origin. Warns if detection fails (tailscale not installed,
        # not logged in, etc.).
        if tailscale:
            ts_origins = _detect_tailscale_origins(resolved_port)
            if ts_origins:
                for origin in ts_origins:
                    if origin not in all_origins:
                        all_origins.append(origin)
                logger.info("Tailscale origin: %s", ts_origins[0])
            else:
                logger.warning(
                    "--tailscale was set but could not detect Tailscale hostname. "
                    "Is Tailscale installed and running? (`tailscale status`)"
                )

        app = create_app(
            manager,
            project_uuid=project_uuid,
            runtime_root=runtime_root,
            transport="tcp",
            host=host,
            port=resolved_port,
            cors_origins=all_origins,
            allow_unsafe_no_permissions=allow_unsafe_no_permissions,
        )
        # Auto-increment port if the default is already in use (try up to +10).
        if port is None:
            for offset in range(11):
                candidate = resolved_port + offset
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind((host, candidate))
                    except OSError as exc:
                        if offset < 10:
                            continue
                        raise RuntimeError(
                            f"Ports {resolved_port}-{candidate} are all in use"
                        ) from exc
                # Port is free — update resolved_port and tailscale origins if
                # the port shifted.
                if candidate != resolved_port:
                    logger.info(
                        "Port %d in use, using %d instead", resolved_port, candidate
                    )
                    if tailscale and all_origins:
                        all_origins = [
                            o.replace(f":{resolved_port}", f":{candidate}")
                            for o in all_origins
                        ]
                    resolved_port = candidate
                    # Rebuild the app with the corrected port so the server
                    # object carries the right value.
                    app = create_app(
                        manager,
                        project_uuid=project_uuid,
                        runtime_root=runtime_root,
                        transport="tcp",
                        host=host,
                        port=resolved_port,
                        cors_origins=all_origins,
                        allow_unsafe_no_permissions=allow_unsafe_no_permissions,
                    )
                break

        port_file = runtime_root / "app.port"
        port_file.parent.mkdir(parents=True, exist_ok=True)
        port_file.write_text(f"{resolved_port}\n", encoding="utf-8")
        print(f"Starting meridian app on http://{host}:{resolved_port}")
        if proxy and proxy.strip():
            print(f"Browser proxy URL: {proxy.strip()}")
        uvicorn_module.run(app, host=host, port=resolved_port, log_level="info")
        return

    socket_path = (uds or "").strip() or str(runtime_root / "app.sock")
    resolved_socket_path = Path(socket_path)
    resolved_socket_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_socket_path.unlink(missing_ok=True)
    app = create_app(
        manager,
        project_uuid=project_uuid,
        runtime_root=runtime_root,
        transport="uds",
        socket_path=str(resolved_socket_path),
        cors_origins=cors_origins or [],
        allow_unsafe_no_permissions=allow_unsafe_no_permissions,
    )

    print(f"Starting meridian app on unix socket: {resolved_socket_path}")
    if proxy and proxy.strip():
        print(f"Browser proxy URL: {proxy.strip()}")
    else:
        print(
            "Browser access requires an HTTP->UDS proxy (for example: "
            f"socat TCP-LISTEN:7676,reuseaddr,fork UNIX-CONNECT:{resolved_socket_path})"
        )
    uvicorn_module.run(app, uds=str(resolved_socket_path), log_level="info")


__all__ = ["run_app"]
