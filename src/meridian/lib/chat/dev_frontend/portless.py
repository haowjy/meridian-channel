"""Portless launcher for ``meridian chat --dev``."""

from __future__ import annotations

import os
import re
import subprocess
import asyncio
from contextlib import suppress
from pathlib import Path

import httpx

from meridian.lib.chat.dev_frontend.launcher import (
    BackendEndpoint,
    FrontendLaunchError,
    FrontendSession,
    PortlessRouteOccupiedError,
)
from meridian.lib.chat.dev_frontend.discovery import detect_tailscale_dns_name
from meridian.lib.chat.dev_frontend.policy import PortlessExposure, PortlessRetryPolicy


_PORTLESS_VAR = re.compile(r"^PORTLESS", re.IGNORECASE)


def _sanitized_portless_env(base_env: dict[str, str]) -> dict[str, str]:
    """Return env with ALL PORTLESS_* vars stripped out."""

    return {key: value for key, value in base_env.items() if not _PORTLESS_VAR.match(key)}


class PortlessLauncher:
    """Launch Vite behind a portless-managed HTTPS route."""

    def __init__(self, *, exposure: PortlessExposure, retry_policy: PortlessRetryPolicy) -> None:
        self._exposure = exposure
        self._retry_policy = retry_policy

    def launch(self, frontend_root: Path, backend: BackendEndpoint) -> FrontendSession:
        """Launch a portless session rooted at ``frontend_root``."""

        env = _sanitized_portless_env(dict(os.environ))
        env.update(
            {
                "VITE_API_PROXY_TARGET": backend.http_origin,
                "VITE_WS_PROXY_TARGET": backend.ws_origin,
            }
        )

        cmd = ["portless", self._exposure.service_name]
        if self._retry_policy.force_takeover:
            cmd.append("--force")
        if self._exposure.share_mode == "tailscale":
            cmd.append("--tailscale")
        if self._exposure.share_mode == "funnel":
            cmd.extend(["--tailscale", "--funnel"])
        cmd.extend(["pnpm", "dev"])

        process = subprocess.Popen(cmd, cwd=frontend_root, env=env)
        try:
            exit_code = process.wait(timeout=self._retry_policy.immediate_exit_window_seconds)
        except subprocess.TimeoutExpired:
            url = _get_portless_url(self._exposure.service_name) or (
                f"https://{self._exposure.service_name}.localhost"
            )
            extra = self._detect_extra_urls()
            return PortlessSession(process=process, url=url, extra_urls=extra)

        if exit_code != 0:
            if self._exposure.share_mode == "local" and not self._retry_policy.force_takeover:
                raise PortlessRouteOccupiedError(
                    f"portless route '{self._exposure.service_name}' appears to be occupied "
                    "by another session.\n\n"
                    "If the previous session is stale, clean it up:\n"
                    "  portless prune\n\n"
                    "To take over the route explicitly:\n"
                    "  meridian chat --dev --portless-force"
                )
            if self._exposure.share_mode == "funnel":
                raise FrontendLaunchError(
                    f"portless failed to start with --funnel (exit code {exit_code}).\n\n"
                    "Funnel prerequisites:\n"
                    "  - Tailscale v1.38.3+, MagicDNS enabled, HTTPS certs enabled\n"
                    "  - Tailnet policy must grant nodeAttrs: funnel to this device\n"
                    "  - Only ports 443, 8443, and 10000 are supported\n\n"
                    "If the route is occupied, try:\n"
                    "  portless prune\n"
                    "  meridian chat --dev --portless-force"
                )
            raise FrontendLaunchError(
                f"portless failed to start (exit code {exit_code}).\n\n"
                "If the route is occupied:\n"
                "  portless prune\n"
                "  meridian chat --dev --portless-force"
            )

        url = _get_portless_url(self._exposure.service_name) or (
            f"https://{self._exposure.service_name}.localhost"
        )
        extra = self._detect_extra_urls()
        return PortlessSession(process=process, url=url, extra_urls=extra)

    def _detect_extra_urls(self) -> dict[str, str]:
        """Build extra URL dict for tailscale/funnel modes."""

        if self._exposure.share_mode not in ("tailscale", "funnel"):
            return {}
        dns_name = detect_tailscale_dns_name()
        if not dns_name:
            return {}
        # Portless uses port 8443 for tailscale HTTPS
        tailscale_url = f"https://{dns_name}:8443"
        label = "Funnel (public)" if self._exposure.share_mode == "funnel" else "Tailscale"
        return {label: tailscale_url}


class PortlessSession:
    """Running portless process managed by the dev supervisor."""

    def __init__(
        self,
        *,
        process: subprocess.Popen[bytes],
        url: str,
        extra_urls: dict[str, str] | None = None,
    ) -> None:
        self._process = process
        self._url = url
        self._extra_urls = extra_urls or {}

    @property
    def url(self) -> str:
        """Browser-facing URL for the dev frontend."""

        return self._url

    @property
    def extra_urls(self) -> dict[str, str]:
        """Additional URLs (e.g. tailscale, funnel)."""

        return self._extra_urls

    async def wait_until_ready(self, timeout: float) -> None:
        """Wait until the portless-managed dev server responds or fails startup."""

        if self._process.poll() is not None:
            raise RuntimeError(
                f"Vite dev server exited during startup with code {self._process.returncode}"
            )
        deadline = asyncio.get_running_loop().time() + timeout
        async with httpx.AsyncClient(timeout=2.0, verify=False) as client:
            while True:
                if self._process.poll() is not None:
                    raise RuntimeError(
                        "Vite dev server exited during startup "
                        f"with code {self._process.returncode}"
                    )
                with suppress(httpx.HTTPError):
                    response = await client.get(self._url)
                    if response.status_code < 500:
                        return
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for portless dev server at {self._url}")
                await asyncio.sleep(0.5)

    def poll(self) -> int | None:
        """Return the process exit code if portless exited, otherwise ``None``."""

        return self._process.poll()

    def terminate(self, grace_period: float = 5.0) -> None:
        """Terminate portless, escalating to kill after ``grace_period`` seconds."""

        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=grace_period)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=grace_period)


def _get_portless_url(name: str) -> str | None:
    """Get the stable URL for a portless-managed service."""

    try:
        result = subprocess.run(
            ["portless", "get", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None
