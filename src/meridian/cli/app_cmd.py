"""CLI command for the meridian app web UI server."""

from __future__ import annotations

import importlib
from pathlib import Path

from meridian.lib.platform import IS_WINDOWS


def run_app(
    uds: str | None = None,
    port: int | None = None,
    host: str = "127.0.0.1",
    proxy: str | None = None,
    debug: bool = False,
    allow_unsafe_no_permissions: bool = False,
) -> None:
    """Start the Meridian app server."""

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
        app = create_app(
            manager,
            project_uuid=project_uuid,
            runtime_root=runtime_root,
            transport="tcp",
            host=host,
            port=resolved_port,
            allow_unsafe_no_permissions=allow_unsafe_no_permissions,
        )
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
