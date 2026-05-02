"""Policy normalization for ``meridian chat --dev`` frontend launchers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from meridian.lib.chat.dev_frontend.discovery import (
    detect_tailscale_dns_name,
    is_portless_available,
)
from meridian.lib.chat.dev_frontend.launcher import FrontendLauncher


@dataclass(frozen=True)
class DevFrontendPolicy:
    """Normalized dev frontend transport and exposure policy."""

    transport: Literal["raw", "portless"]
    exposure: Literal["local", "tailscale", "funnel"]
    force_takeover: bool = False


@dataclass(frozen=True)
class RawViteExposure:
    """Network exposure policy for a raw Vite dev server."""

    bind_host: str = "127.0.0.1"
    allowed_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortlessExposure:
    """Network exposure policy for a portless-managed Vite dev server."""

    service_name: str = "app.meridian"
    share_mode: Literal["local", "tailscale", "funnel"] = "local"
    allowed_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortlessRetryPolicy:
    """Startup collision policy for a portless-managed dev server."""

    immediate_exit_window_seconds: float = 2.0
    force_takeover: bool = False


class DevFrontendConfigurationError(ValueError):
    """Raised for invalid CLI flag combinations."""


def resolve_dev_frontend_launcher(
    *,
    backend_host: str,
    no_portless: bool,
    tailscale: bool,
    funnel: bool,
    force_takeover: bool,
    portless_available: bool | None = None,
) -> FrontendLauncher:
    """Validate CLI policy and build the matching frontend launcher."""

    available = is_portless_available() if portless_available is None else portless_available

    if no_portless and (tailscale or funnel):
        raise DevFrontendConfigurationError(
            "--no-portless cannot be combined with --tailscale or --funnel"
        )
    if tailscale and funnel:
        raise DevFrontendConfigurationError(
            "--tailscale and --funnel cannot be combined; --funnel already implies Tailscale"
        )
    if (tailscale or funnel) and not available:
        raise DevFrontendConfigurationError(
            "--tailscale/--funnel require portless, but the portless executable was not found"
        )

    use_portless = available and not no_portless
    if force_takeover and not use_portless:
        raise DevFrontendConfigurationError("--portless-force requires effective portless dev mode")

    exposure: Literal["local", "tailscale", "funnel"] = "local"
    if funnel:
        exposure = "funnel"
    elif tailscale:
        exposure = "tailscale"

    _policy = DevFrontendPolicy(
        transport="portless" if use_portless else "raw",
        exposure=exposure,
        force_takeover=force_takeover,
    )

    if _policy.transport == "raw":
        from meridian.lib.chat.dev_frontend.raw_vite import RawViteLauncher

        allowed_hosts: tuple[str, ...] = ()
        if backend_host in ("0.0.0.0", "::"):
            dns_name = detect_tailscale_dns_name()
            if dns_name is not None:
                allowed_hosts = (dns_name,)
        return RawViteLauncher(
            exposure=RawViteExposure(bind_host=backend_host, allowed_hosts=allowed_hosts)
        )

    from meridian.lib.chat.dev_frontend.portless import PortlessLauncher

    portless_allowed_hosts: tuple[str, ...] = ()
    if _policy.exposure in ("tailscale", "funnel"):
        dns_name = detect_tailscale_dns_name()
        if dns_name is not None:
            portless_allowed_hosts = (dns_name,)

    return PortlessLauncher(
        exposure=PortlessExposure(
            share_mode=_policy.exposure,
            allowed_hosts=portless_allowed_hosts,
        ),
        retry_policy=PortlessRetryPolicy(force_takeover=_policy.force_takeover),
    )
