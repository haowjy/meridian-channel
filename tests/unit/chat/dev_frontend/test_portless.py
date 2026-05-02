import subprocess
from types import SimpleNamespace

import httpx
import pytest

from meridian.lib.chat.dev_frontend.launcher import (
    BackendEndpoint,
    FrontendLaunchError,
    PortlessRouteOccupiedError,
)
from meridian.lib.chat.dev_frontend.policy import PortlessExposure, PortlessRetryPolicy
from meridian.lib.chat.dev_frontend.portless import (
    PortlessLauncher,
    PortlessSession,
    _sanitized_portless_env,
)


async def _async_noop(_delay: float) -> None:
    return None


class FakeLoop:
    def __init__(self, *times: float):
        self._times = iter(times)
        self._last = times[-1] if times else 0.0

    def time(self) -> float:
        try:
            self._last = next(self._times)
        except StopIteration:
            pass
        return self._last


class FakeAsyncClient:
    def __init__(self, responses):
        self._responses = iter(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _url: str):
        result = next(self._responses)
        if isinstance(result, Exception):
            raise result
        return result


class FakeProcess:
    def __init__(self, *, wait_result=None, poll_results=None, returncode=0):
        self._wait_result = wait_result
        self._poll_results = iter(poll_results or [None])
        self.returncode = returncode
        self.wait_calls = []
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if isinstance(self._wait_result, BaseException):
            raise self._wait_result
        return self._wait_result

    def poll(self):
        try:
            return next(self._poll_results)
        except StopIteration:
            return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


@pytest.fixture
def backend_endpoint() -> BackendEndpoint:
    return BackendEndpoint(
        bind_host="127.0.0.1",
        port=9000,
        client_host="127.0.0.1",
        http_origin="http://127.0.0.1:9000",
        ws_origin="ws://127.0.0.1:9000",
    )


def test_sanitized_portless_env_removes_all_portless_variables():
    env = {
        "PORTLESS_URL": "https://old",
        "portless_debug": "1",
        "PoRtLeSs_token": "secret",
        "PATH": "/bin",
    }

    sanitized = _sanitized_portless_env(env)

    assert sanitized == {"PATH": "/bin"}


@pytest.mark.parametrize(
    ("share_mode", "force_takeover", "expected_prefix"),
    [
        ("local", False, ["portless", "app.meridian", "pnpm", "dev"]),
        (
            "tailscale",
            False,
            ["portless", "app.meridian", "--tailscale", "pnpm", "dev"],
        ),
        (
            "funnel",
            True,
            [
                "portless",
                "app.meridian",
                "--force",
                "--tailscale",
                "--funnel",
                "pnpm",
                "dev",
            ],
        ),
    ],
)
def test_portless_launcher_scrubs_inherited_env_and_builds_expected_command(
    monkeypatch,
    tmp_path,
    backend_endpoint: BackendEndpoint,
    share_mode: str,
    force_takeover: bool,
    expected_prefix: list[str],
):
    frontend_root = tmp_path / "frontend"
    frontend_root.mkdir()
    process = FakeProcess(wait_result=subprocess.TimeoutExpired(cmd="portless", timeout=2), returncode=0)
    popen_calls = []

    monkeypatch.setenv("PORTLESS_URL", "https://polluted")
    monkeypatch.setenv("PORTLESS_DEBUG", "1")
    monkeypatch.setenv("VITE_API_PROXY_TARGET", "http://wrong")
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.subprocess.Popen",
        lambda cmd, cwd, env: popen_calls.append((cmd, cwd, env)) or process,
    )
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless._get_portless_url",
        lambda name: f"https://{name}.example.test",
    )

    launcher = PortlessLauncher(
        exposure=PortlessExposure(share_mode=share_mode),
        retry_policy=PortlessRetryPolicy(force_takeover=force_takeover),
    )

    session = launcher.launch(frontend_root, backend_endpoint)

    (cmd, cwd, env), = popen_calls
    assert cmd == expected_prefix
    assert cwd == frontend_root
    assert env["VITE_API_PROXY_TARGET"] == backend_endpoint.http_origin
    assert env["VITE_WS_PROXY_TARGET"] == backend_endpoint.ws_origin
    assert "PORTLESS_URL" not in env
    assert "PORTLESS_DEBUG" not in env
    assert session.url == "https://app.meridian.example.test"


def test_portless_launcher_uses_default_url_when_lookup_missing(
    monkeypatch, tmp_path, backend_endpoint: BackendEndpoint
):
    frontend_root = tmp_path / "frontend"
    frontend_root.mkdir()
    process = FakeProcess(wait_result=subprocess.TimeoutExpired(cmd="portless", timeout=2), returncode=0)

    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.subprocess.Popen",
        lambda cmd, cwd, env: process,
    )
    monkeypatch.setattr("meridian.lib.chat.dev_frontend.portless._get_portless_url", lambda name: None)

    session = PortlessLauncher(
        exposure=PortlessExposure(service_name="custom"),
        retry_policy=PortlessRetryPolicy(),
    ).launch(frontend_root, backend_endpoint)

    assert session.url == "https://custom.localhost"


def test_portless_launcher_raises_route_occupied_for_local_immediate_exit(
    monkeypatch, tmp_path, backend_endpoint: BackendEndpoint
):
    frontend_root = tmp_path / "frontend"
    frontend_root.mkdir()
    process = FakeProcess(wait_result=1, returncode=1)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.subprocess.Popen",
        lambda cmd, cwd, env: process,
    )

    launcher = PortlessLauncher(
        exposure=PortlessExposure(share_mode="local"),
        retry_policy=PortlessRetryPolicy(force_takeover=False),
    )

    with pytest.raises(PortlessRouteOccupiedError, match="portless route 'app\\.meridian' appears"):
        launcher.launch(frontend_root, backend_endpoint)


def test_portless_launcher_raises_funnel_specific_error_on_failure(
    monkeypatch, tmp_path, backend_endpoint: BackendEndpoint
):
    frontend_root = tmp_path / "frontend"
    frontend_root.mkdir()
    process = FakeProcess(wait_result=7, returncode=7)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.subprocess.Popen",
        lambda cmd, cwd, env: process,
    )

    launcher = PortlessLauncher(
        exposure=PortlessExposure(share_mode="funnel"),
        retry_policy=PortlessRetryPolicy(force_takeover=False),
    )

    with pytest.raises(FrontendLaunchError, match=r"portless failed to start with --funnel \(exit code 7\)"):
        launcher.launch(frontend_root, backend_endpoint)


def test_portless_launcher_raises_generic_error_when_force_takeover_startup_fails(
    monkeypatch, tmp_path, backend_endpoint: BackendEndpoint
):
    frontend_root = tmp_path / "frontend"
    frontend_root.mkdir()
    process = FakeProcess(wait_result=5, returncode=5)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.subprocess.Popen",
        lambda cmd, cwd, env: process,
    )

    launcher = PortlessLauncher(
        exposure=PortlessExposure(share_mode="local"),
        retry_policy=PortlessRetryPolicy(force_takeover=True),
    )

    with pytest.raises(FrontendLaunchError, match=r"portless failed to start \(exit code 5\)"):
        launcher.launch(frontend_root, backend_endpoint)


@pytest.mark.asyncio
async def test_portless_session_wait_until_ready_returns_after_non_5xx_response(monkeypatch):
    session = PortlessSession(
        process=FakeProcess(poll_results=[None, None, None, None], returncode=0),
        url="https://app.meridian.example.test",
    )
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient([httpx.ConnectError("not yet"), SimpleNamespace(status_code=404)]),
    )
    monkeypatch.setattr("meridian.lib.chat.dev_frontend.portless.asyncio.sleep", _async_noop)
    loop = FakeLoop(0.0, 0.1, 0.2)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.asyncio.get_running_loop",
        lambda: loop,
    )

    await session.wait_until_ready(timeout=1.0)


@pytest.mark.asyncio
async def test_portless_session_wait_until_ready_fails_if_process_crashes(monkeypatch):
    session = PortlessSession(
        process=FakeProcess(poll_results=[None, 9], returncode=9),
        url="https://app.meridian.example.test",
    )
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient([httpx.ConnectError("not yet")]),
    )
    monkeypatch.setattr("meridian.lib.chat.dev_frontend.portless.asyncio.sleep", _async_noop)
    loop = FakeLoop(0.0, 0.1, 0.2)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.asyncio.get_running_loop",
        lambda: loop,
    )

    with pytest.raises(RuntimeError, match="Vite dev server exited during startup with code 9"):
        await session.wait_until_ready(timeout=1.0)


@pytest.mark.asyncio
async def test_portless_session_wait_until_ready_times_out(monkeypatch):
    session = PortlessSession(
        process=FakeProcess(poll_results=[None, None, None], returncode=0),
        url="https://app.meridian.example.test",
    )
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient([httpx.ConnectError("not yet"), httpx.ConnectError("still not"), httpx.ConnectError("again")]),
    )
    monkeypatch.setattr("meridian.lib.chat.dev_frontend.portless.asyncio.sleep", _async_noop)
    loop = FakeLoop(0.0, 0.4, 0.6)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.portless.asyncio.get_running_loop",
        lambda: loop,
    )

    with pytest.raises(TimeoutError, match="Timed out waiting for portless dev server"):
        await session.wait_until_ready(timeout=0.5)
