import pytest

from meridian.lib.chat.dev_frontend.policy import (
    DevFrontendConfigurationError,
    PortlessExposure,
    PortlessRetryPolicy,
    RawViteExposure,
    resolve_dev_frontend_launcher,
)
from meridian.lib.chat.dev_frontend.portless import PortlessLauncher
from meridian.lib.chat.dev_frontend.raw_vite import RawViteLauncher


@pytest.mark.parametrize(
    ("no_portless", "tailscale", "funnel", "message"),
    [
        (True, True, False, "--no-portless cannot be combined with --tailscale or --funnel"),
        (True, False, True, "--no-portless cannot be combined with --tailscale or --funnel"),
        (
            False,
            True,
            True,
            "--tailscale and --funnel cannot be combined; --funnel already implies Tailscale",
        ),
    ],
)
def test_resolve_dev_frontend_launcher_rejects_invalid_flag_combinations(
    no_portless: bool, tailscale: bool, funnel: bool, message: str
):
    with pytest.raises(DevFrontendConfigurationError, match=message):
        resolve_dev_frontend_launcher(
            backend_host="127.0.0.1",
            no_portless=no_portless,
            tailscale=tailscale,
            funnel=funnel,
            force_takeover=False,
            portless_available=True,
        )


@pytest.mark.parametrize("tailscale,funnel", [(True, False), (False, True)])
def test_resolve_dev_frontend_launcher_rejects_sharing_without_portless(
    tailscale: bool, funnel: bool
):
    with pytest.raises(
        DevFrontendConfigurationError,
        match="--tailscale/--funnel require portless, but the portless executable was not found",
    ):
        resolve_dev_frontend_launcher(
            backend_host="127.0.0.1",
            no_portless=False,
            tailscale=tailscale,
            funnel=funnel,
            force_takeover=False,
            portless_available=False,
        )


@pytest.mark.parametrize(
    ("portless_available", "no_portless"),
    [(False, False), (True, True)],
)
def test_resolve_dev_frontend_launcher_uses_raw_vite_when_portless_not_effective(
    monkeypatch, portless_available: bool, no_portless: bool
):
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.policy.detect_tailscale_dns_name",
        lambda: "tailnet.example.ts.net",
    )

    launcher = resolve_dev_frontend_launcher(
        backend_host="0.0.0.0",
        no_portless=no_portless,
        tailscale=False,
        funnel=False,
        force_takeover=False,
        portless_available=portless_available,
    )

    assert isinstance(launcher, RawViteLauncher)
    assert launcher.exposure == RawViteExposure(
        bind_host="0.0.0.0", allowed_hosts=("tailnet.example.ts.net",)
    )


def test_resolve_dev_frontend_launcher_does_not_set_raw_allowed_hosts_without_dns(monkeypatch):
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.policy.detect_tailscale_dns_name", lambda: None
    )

    launcher = resolve_dev_frontend_launcher(
        backend_host="::",
        no_portless=True,
        tailscale=False,
        funnel=False,
        force_takeover=False,
        portless_available=True,
    )

    assert isinstance(launcher, RawViteLauncher)
    assert launcher.exposure == RawViteExposure(bind_host="::", allowed_hosts=())


def test_resolve_dev_frontend_launcher_keeps_loopback_raw_vite_local(monkeypatch):
    detect_calls = []
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.policy.detect_tailscale_dns_name",
        lambda: detect_calls.append(True) or "unused.ts.net",
    )

    launcher = resolve_dev_frontend_launcher(
        backend_host="127.0.0.1",
        no_portless=True,
        tailscale=False,
        funnel=False,
        force_takeover=False,
        portless_available=True,
    )

    assert isinstance(launcher, RawViteLauncher)
    assert launcher.exposure == RawViteExposure(bind_host="127.0.0.1", allowed_hosts=())
    assert detect_calls == []


@pytest.mark.parametrize(
    ("tailscale", "funnel", "share_mode"),
    [
        (False, False, "local"),
        (True, False, "tailscale"),
        (False, True, "funnel"),
    ],
)
def test_resolve_dev_frontend_launcher_builds_portless_policy(
    monkeypatch, tailscale: bool, funnel: bool, share_mode: str
):
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.policy.detect_tailscale_dns_name",
        lambda: "tailnet.example.ts.net",
    )

    launcher = resolve_dev_frontend_launcher(
        backend_host="127.0.0.1",
        no_portless=False,
        tailscale=tailscale,
        funnel=funnel,
        force_takeover=funnel,
        portless_available=True,
    )

    expected_hosts = ("tailnet.example.ts.net",) if share_mode != "local" else ()
    assert isinstance(launcher, PortlessLauncher)
    assert launcher._exposure == PortlessExposure(
        share_mode=share_mode, allowed_hosts=expected_hosts
    )
    assert launcher._retry_policy == PortlessRetryPolicy(force_takeover=funnel)


@pytest.mark.parametrize(
    ("portless_available", "no_portless"),
    [(False, False), (True, True)],
)
def test_resolve_dev_frontend_launcher_rejects_force_takeover_without_effective_portless(
    portless_available: bool, no_portless: bool
):
    with pytest.raises(
        DevFrontendConfigurationError,
        match="--portless-force requires effective portless dev mode",
    ):
        resolve_dev_frontend_launcher(
            backend_host="127.0.0.1",
            no_portless=no_portless,
            tailscale=False,
            funnel=False,
            force_takeover=True,
            portless_available=portless_available,
        )
