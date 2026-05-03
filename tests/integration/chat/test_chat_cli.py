from __future__ import annotations

import importlib
import os
from io import StringIO
from pathlib import Path
from typing import cast

import pytest

from meridian.cli import chat_cmd
from meridian.cli.chat_cmd import run_chat_server
from meridian.cli.output import OutputConfig
from meridian.lib.harness.ids import HarnessId

cli_main = importlib.import_module("meridian.cli.main")


class EmptyPipelineLookup:
    def get_pipeline(self, chat_id: str):
        _ = chat_id
        return None


class _UnexpectedCall(RuntimeError):
    pass


class _FakeLauncher:
    pass


def test_chat_cli_auto_port_prints_local_backend_url(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: tmp_path / "runtime")
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_run(app, *, host: str, port: int) -> None:
        calls.append({"app": app, "host": host, "port": port})

    stdout = StringIO()
    actual_port = run_chat_server(
        host="127.0.0.1",
        port=0,
        model="test-model",
        harness="claude",
        headless=True,
        uvicorn_run=fake_run,
        stdout=stdout,
    )

    assert actual_port > 0
    assert stdout.getvalue() == f"Chat backend: http://127.0.0.1:{actual_port}\n"
    assert len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == actual_port


def test_chat_cli_uses_requested_host_and_port(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: tmp_path / "runtime")
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[str, int]] = []

    def fake_run(_app, *, host: str, port: int) -> None:
        calls.append((host, port))

    stdout = StringIO()
    actual_port = run_chat_server(
        host="0.0.0.0",
        port=8765,
        harness="codex",
        headless=True,
        uvicorn_run=fake_run,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert calls == [("0.0.0.0", 8765)]
    assert stdout.getvalue() == "Chat backend: http://127.0.0.1:8765\n"


@pytest.mark.parametrize("harness", ["claude", "codex", "opencode"])
def test_chat_cli_accepts_supported_harness_matrix(monkeypatch, tmp_path, harness: str) -> None:
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: tmp_path / harness)
    monkeypatch.chdir(tmp_path)

    run_chat_server(
        harness=harness,
        port=8900,
        headless=True,
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=StringIO(),
    )


def test_chat_cli_rejects_unknown_harness(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: tmp_path / "runtime")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="unsupported chat harness"):
        run_chat_server(
            harness="bogus",
            port=8900,
            headless=True,
            uvicorn_run=lambda *_args, **_kwargs: None,
            stdout=StringIO(),
        )


def _write_dist(root: Path) -> Path:
    dist = root / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>chat ui</html>", encoding="utf-8")
    (assets / "index.js").write_text("console.log('chat')", encoding="utf-8")
    return dist


def _write_dev_frontend(root: Path) -> Path:
    frontend_root = root / "meridian-web"
    (frontend_root / "node_modules").mkdir(parents=True)
    (frontend_root / "package.json").write_text('{"scripts":{"dev":"vite"}}', encoding="utf-8")
    return frontend_root


def test_chat_cli_static_mode_mounts_assets_and_writes_server_discovery(
    monkeypatch, tmp_path
) -> None:
    runtime_root = tmp_path / "runtime"
    dist = _write_dist(tmp_path)
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.chdir(tmp_path)
    mounted: dict[str, object] = {}

    def fake_mount(app, assets) -> None:
        mounted["app"] = app
        mounted["assets"] = assets

    monkeypatch.setattr("meridian.lib.chat.server.mount_frontend", fake_mount)
    stdout = StringIO()

    actual_port = run_chat_server(
        host="0.0.0.0",
        port=8765,
        frontend_dist=str(dist),
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert stdout.getvalue().splitlines()[-1] == "Chat UI: http://127.0.0.1:8765"
    assert cast("object", mounted["assets"]).root == dist.resolve()
    discovery = runtime_root / "chat-server.json"
    assert discovery.exists()
    assert '"url": "http://127.0.0.1:8765"' in discovery.read_text(encoding="utf-8")


def test_chat_cli_static_mode_uses_default_asset_resolution(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    dist = _write_dist(tmp_path)
    assets = chat_cmd.FrontendAssets(
        root=dist, index_html=dist / "index.html", assets_dir=dist / "assets"
    )
    mounted: dict[str, object] = {}

    def fake_mount(app, resolved_assets) -> None:
        mounted["app"] = app
        mounted["assets"] = resolved_assets

    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.setattr(chat_cmd, "resolve_frontend_assets", lambda explicit_dist=None: assets)
    monkeypatch.setattr("meridian.lib.chat.server.mount_frontend", fake_mount)
    stdout = StringIO()

    actual_port = run_chat_server(
        port=8765,
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert mounted["assets"] == assets
    assert stdout.getvalue() == "Chat UI: http://127.0.0.1:8765\n"
    discovery = runtime_root / "chat-server.json"
    assert discovery.exists()
    assert '"url": "http://127.0.0.1:8765"' in discovery.read_text(encoding="utf-8")


def test_chat_cli_headless_skips_frontend_serving(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()

    actual_port = run_chat_server(
        host="127.0.0.1",
        port=8765,
        headless=True,
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert stdout.getvalue() == "Chat backend: http://127.0.0.1:8765\n"


def test_chat_cli_missing_assets_exits_with_actionable_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: tmp_path / "runtime")
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(
            port=8765,
            frontend_dist=str(tmp_path / "missing"),
            uvicorn_run=lambda *_args, **_kwargs: None,
            stdout=stdout,
        )

    assert exc_info.value.code == 1
    output = stdout.getvalue()
    assert "Built frontend assets not found" in output
    assert "meridian chat --frontend-dist /path/to/dist" in output
    assert "meridian chat --headless" in output


def test_chat_cli_default_static_mode_falls_back_to_headless_when_assets_do_not_resolve(
    monkeypatch, tmp_path
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.setattr(chat_cmd, "resolve_frontend_assets", lambda explicit_dist=None: None)
    stdout = StringIO()
    calls: list[tuple[str, int]] = []

    def fake_run(_app, *, host: str, port: int) -> None:
        calls.append((host, port))

    actual_port = run_chat_server(port=8765, uvicorn_run=fake_run, stdout=stdout)

    assert actual_port == 8765
    assert calls == [("127.0.0.1", 8765)]
    assert stdout.getvalue() == (
        "Note: Frontend assets not found. Running in headless mode.\n"
        "To serve the UI, build assets first: cd ../meridian-web && pnpm build\n"
        "Chat backend: http://127.0.0.1:8765\n"
    )


def test_chat_ls_uses_discovered_server_url(monkeypatch, tmp_path, capsys) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "chat-server.json").write_text(
        '{"url":"http://127.0.0.1:9999"}\n', encoding="utf-8"
    )
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)

    def fake_request(method, path, *, timeout):
        assert method == "GET"
        assert path == "http://127.0.0.1:9999/chat"
        assert timeout == 5.0

        class Response:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "chats": [
                        {"chat_id": "c-1", "state": "idle", "created_at": "2026-04-30T00:00:00Z"}
                    ]
                }

        return Response()

    monkeypatch.setattr("httpx.request", fake_request)

    chat_cmd._chat_ls()

    output = capsys.readouterr().out
    assert "chat_id" in output
    assert "c-1" in output
    assert "idle" in output


def test_chat_command_falls_back_to_globally_parsed_harness(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chat_server(**kwargs) -> int:
        captured.update(kwargs)
        return 8765

    monkeypatch.setattr(chat_cmd, "run_chat_server", fake_run_chat_server)
    token = cli_main._GLOBAL_OPTIONS.set(
        cli_main.GlobalOptions(output=OutputConfig(format="text"), harness="codex")
    )
    try:
        chat_cmd._chat(port=8765)
    finally:
        cli_main._GLOBAL_OPTIONS.reset(token)

    assert captured["harness"] == "codex"
    assert captured["headless"] is False
    assert captured["frontend_dist"] is None
    assert captured["open_browser"] is False


def test_chat_command_prefers_explicit_harness_over_global_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chat_server(**kwargs) -> int:
        captured.update(kwargs)
        return 8765

    monkeypatch.setattr(chat_cmd, "run_chat_server", fake_run_chat_server)
    token = cli_main._GLOBAL_OPTIONS.set(
        cli_main.GlobalOptions(output=OutputConfig(format="text"), harness="claude")
    )
    try:
        chat_cmd._chat(
            harness="opencode",
            port=8765,
            headless=True,
            frontend_dist="/tmp/dist",
            open_browser=True,
        )
    finally:
        cli_main._GLOBAL_OPTIONS.reset(token)

    assert captured["harness"] == "opencode"
    assert captured["headless"] is True
    assert captured["frontend_dist"] == "/tmp/dist"
    assert captured["open_browser"] is True


@pytest.mark.parametrize("harness", [HarnessId.CLAUDE, HarnessId.CODEX, HarnessId.OPENCODE])
def test_backend_acquisition_preserves_requested_harness(tmp_path, harness: HarnessId) -> None:
    acquisition = chat_cmd._build_backend_acquisition(
        runtime_root=tmp_path / "runtime",
        project_root=tmp_path,
        harness_id=harness,
        model="model-x",
        pipeline_lookup=EmptyPipelineLookup(),
    )

    config = acquisition._build_connection_config("c1", "hello")
    spec = acquisition._build_launch_spec("hello")

    assert config.harness_id == harness
    assert spec.model == "model-x"


@pytest.mark.parametrize(
    ("harness_name", "expected_harness"),
    [
        ("claude", HarnessId.CLAUDE),
        ("codex", HarnessId.CODEX),
        ("opencode", HarnessId.OPENCODE),
    ],
)
def test_chat_cli_builds_runtime_with_factory_inputs(
    monkeypatch, tmp_path, harness_name: str, expected_harness: HarnessId
) -> None:
    runtime_root = tmp_path / "runtime"
    captured: dict[str, object] = {}

    class FakeRuntime:
        def __init__(self, *, runtime_root, project_root, acquisition_factory) -> None:
            captured["runtime_root"] = runtime_root
            captured["project_root"] = project_root
            captured["acquisition_factory"] = acquisition_factory
            captured["runtime"] = self

    def fake_configure(*, runtime) -> None:
        captured["configured_runtime"] = runtime

    monkeypatch.setattr(chat_cmd, "ChatRuntime", FakeRuntime)
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.setattr(chat_cmd, "resolve_project_root", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    import meridian.lib.chat.server as chat_server

    monkeypatch.setattr(chat_server, "configure", fake_configure)
    monkeypatch.setattr(chat_server, "app", object())

    run_chat_server(
        harness=harness_name,
        model="model-x",
        port=8900,
        headless=True,
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=StringIO(),
    )

    assert captured["runtime_root"] == runtime_root
    assert captured["project_root"] == tmp_path
    assert captured["configured_runtime"] is captured["runtime"]

    factory = cast("chat_cmd._ChatBackendAcquisitionFactory", captured["acquisition_factory"])
    assert factory.harness_id == expected_harness
    assert factory.model == "model-x"

    acquisition = factory.build(
        pipeline_lookup=EmptyPipelineLookup(),
        project_root=tmp_path,
        runtime_root=runtime_root,
    )
    config = acquisition._build_connection_config("c1", "hello")
    spec = acquisition._build_launch_spec("hello")

    assert config.harness_id == expected_harness
    assert config.project_root == tmp_path
    assert spec.model == "model-x"


def test_stale_asset_warning_mentions_rebuild(monkeypatch, tmp_path) -> None:
    project = tmp_path / "meridian-cli"
    source_dir = tmp_path / "meridian-web" / "src"
    source_dir.mkdir(parents=True)
    dist = _write_dist(tmp_path)
    index = dist / "index.html"
    source_file = source_dir / "App.tsx"
    source_file.write_text("export function App() { return null }", encoding="utf-8")
    newer = index.stat().st_mtime + 10
    os.utime(source_file, (newer, newer))
    monkeypatch.setattr(chat_cmd, "resolve_project_root", lambda: project)

    stdout = StringIO()
    chat_cmd._check_stale_assets(
        chat_cmd.FrontendAssets(root=dist, index_html=index, assets_dir=dist / "assets"),
        stdout,
    )

    assert "Frontend source is newer than built assets" in stdout.getvalue()
    assert "pnpm build" in stdout.getvalue()


def test_chat_command_meridian_env_dev_enables_dev_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chat_server(**kwargs) -> int:
        captured.update(kwargs)
        return 8765

    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    monkeypatch.setattr(chat_cmd, "run_chat_server", fake_run_chat_server)
    token = cli_main._GLOBAL_OPTIONS.set(
        cli_main.GlobalOptions(output=OutputConfig(format="text"), harness="claude")
    )
    try:
        chat_cmd._chat(port=8765)
    finally:
        cli_main._GLOBAL_OPTIONS.reset(token)

    assert captured["dev"] is True
    assert captured["frontend_root"] is None


def test_chat_command_headless_takes_precedence_over_meridian_env_dev(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chat_server(**kwargs) -> int:
        captured.update(kwargs)
        return 8765

    monkeypatch.setenv("MERIDIAN_ENV", "dev")
    monkeypatch.setattr(chat_cmd, "run_chat_server", fake_run_chat_server)
    token = cli_main._GLOBAL_OPTIONS.set(
        cli_main.GlobalOptions(output=OutputConfig(format="text"), harness="claude")
    )
    try:
        chat_cmd._chat(port=8765, headless=True)
    finally:
        cli_main._GLOBAL_OPTIONS.reset(token)

    assert captured["headless"] is True
    assert captured["dev"] is False


@pytest.mark.parametrize(
    ("kwargs", "expected_error"),
    [
        (
            {"dev": True, "frontend_dist": "/tmp/dist"},
            "Error: --frontend-dist cannot be combined with --dev.\n",
        ),
        (
            {"frontend_root": "/tmp/frontend"},
            "Error: --frontend-root is only valid with --dev.\n",
        ),
        ({"no_portless": True}, "Error: --no-portless is only valid with --dev.\n"),
        ({"tailscale": True}, "Error: --tailscale and --funnel are only valid with --dev.\n"),
        ({"funnel": True}, "Error: --tailscale and --funnel are only valid with --dev.\n"),
        (
            {"portless_force": True},
            "Error: --portless-force is only valid with portless dev mode.\n",
        ),
    ],
)
def test_chat_cli_rejects_invalid_flag_combinations_before_startup(
    monkeypatch, tmp_path, kwargs: dict[str, object], expected_error: str
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()
    launch_attempts: list[str] = []

    def forbid(*_args, **_kwargs):
        launch_attempts.append("called")
        raise _UnexpectedCall("startup collaborator should not run")

    monkeypatch.setattr(chat_cmd, "resolve_frontend_assets", forbid)

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(
            port=8765,
            uvicorn_run=forbid,
            stdout=stdout,
            **kwargs,
        )

    assert exc_info.value.code == 1
    assert stdout.getvalue() == expected_error
    assert launch_attempts == []


def test_chat_cli_headless_rejects_dev_mode(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(
            port=8765,
            headless=True,
            dev=True,
            uvicorn_run=lambda *_args, **_kwargs: None,
            stdout=stdout,
        )

    assert exc_info.value.code == 1
    assert stdout.getvalue() == "Error: --dev cannot be combined with --headless.\n"


@pytest.mark.parametrize(
    ("kwargs", "expected_error"),
    [
        (
            {"headless": True, "no_portless": True},
            "Error: --no-portless is only valid with --dev.\n",
        ),
        (
            {"headless": True, "tailscale": True},
            "Error: --tailscale and --funnel are only valid with --dev.\n",
        ),
        (
            {"headless": True, "funnel": True},
            "Error: --tailscale and --funnel are only valid with --dev.\n",
        ),
        (
            {"headless": True, "portless_force": True},
            "Error: dev frontend flags cannot be combined with --headless.\n",
        ),
    ],
)
def test_chat_cli_headless_rejects_dev_frontend_flags(
    monkeypatch, tmp_path, kwargs, expected_error: str
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    stdout = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(port=8765, stdout=stdout, **kwargs)

    assert exc_info.value.code == 1
    assert stdout.getvalue() == expected_error


def test_chat_cli_dev_mode_reports_missing_frontend_checkout_actionably(
    monkeypatch, tmp_path
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.resolve_dev_frontend_root",
        lambda *, explicit=None: None,
    )
    stdout = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(port=8765, dev=True, stdout=stdout)

    assert exc_info.value.code == 1
    output = stdout.getvalue()
    assert "Error: Dev frontend checkout not found." in output
    assert "--frontend-root /path/to/meridian-web" in output
    assert "MERIDIAN_DEV_FRONTEND_ROOT=/path/to/meridian-web" in output
    assert "meridian chat --headless" in output


def test_chat_cli_dev_mode_reports_prerequisite_failures(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    frontend_root = tmp_path / "meridian-web"
    frontend_root.mkdir()
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    stdout = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(
            port=8765,
            dev=True,
            frontend_root=str(frontend_root),
            stdout=stdout,
        )

    assert exc_info.value.code == 1
    expected = f"Error: Frontend root is missing package.json: {frontend_root.resolve()}\n"
    assert stdout.getvalue() == expected


def test_chat_cli_dev_mode_surfaces_launcher_configuration_errors(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    stdout = StringIO()

    def raise_config_error(**_kwargs):
        from meridian.lib.chat.dev_frontend import DevFrontendConfigurationError

        raise DevFrontendConfigurationError("--tailscale/--funnel require portless")

    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.resolve_dev_frontend_launcher",
        raise_config_error,
    )

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(port=8765, dev=True, stdout=stdout)

    assert exc_info.value.code == 1
    assert stdout.getvalue() == "Error: --tailscale/--funnel require portless\n"


def test_chat_cli_dev_mode_uses_frontend_root_launcher_supervisor_and_warning(
    monkeypatch, tmp_path
) -> None:
    runtime_root = tmp_path / "runtime"
    frontend_root = _write_dev_frontend(tmp_path)
    launcher = _FakeLauncher()
    captured: dict[str, object] = {}

    class FakeSupervisor:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        async def run(self) -> int:
            captured["ran"] = True
            return 0

    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.setattr(
        "meridian.lib.chat.dev_frontend.resolve_dev_frontend_launcher",
        lambda **_kwargs: launcher,
    )
    monkeypatch.setattr("meridian.lib.chat.dev_frontend.DevSupervisor", FakeSupervisor)
    stdout = StringIO()

    actual_port = run_chat_server(
        host="0.0.0.0",
        port=8765,
        dev=True,
        frontend_root=str(frontend_root),
        open_browser=True,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert captured["backend_host"] == "0.0.0.0"
    assert captured["backend_port"] == 8765
    assert captured["frontend_root"] == frontend_root.resolve()
    assert captured["open_browser"] is True
    assert captured["launcher"] is launcher
    assert captured["ran"] is True
    assert stdout.getvalue() == (
        "Warning: Backend is bound to all interfaces."
        " The frontend sharing mode does not restrict backend API access.\n"
    )
    discovery = runtime_root / "chat-server.json"
    assert discovery.exists()
    assert '"url": "http://127.0.0.1:8765"' in discovery.read_text(encoding="utf-8")


def test_chat_cli_dev_mode_surfaces_frontend_launch_errors(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    frontend_root = _write_dev_frontend(tmp_path)

    class FakeSupervisor:
        def __init__(self, **_kwargs) -> None:
            pass

        async def run(self) -> int:
            from meridian.lib.chat.dev_frontend.launcher import FrontendLaunchError

            raise FrontendLaunchError("portless failed to start")

    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.setattr("meridian.lib.chat.dev_frontend.DevSupervisor", FakeSupervisor)
    stdout = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_chat_server(
            port=8765,
            dev=True,
            frontend_root=str(frontend_root),
            stdout=stdout,
        )

    assert exc_info.value.code == 1
    assert stdout.getvalue() == "Error: portless failed to start\n"


def test_chat_cli_headless_warns_on_open(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()
    opened: list[str] = []
    monkeypatch.setattr(chat_cmd.webbrowser, "open", lambda url: opened.append(url))

    actual_port = run_chat_server(
        port=8765,
        headless=True,
        open_browser=True,
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert opened == []
    assert stdout.getvalue() == (
        "Warning: --open is ignored in headless mode.\n"
        "Chat backend: http://127.0.0.1:8765\n"
    )
