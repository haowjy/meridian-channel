from __future__ import annotations

import importlib
from io import StringIO
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
        uvicorn_run=fake_run,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert calls == [("0.0.0.0", 8765)]
    assert stdout.getvalue() == "Chat backend: http://0.0.0.0:8765\n"


@pytest.mark.parametrize("harness", ["claude", "codex", "opencode"])
def test_chat_cli_accepts_supported_harness_matrix(monkeypatch, tmp_path, harness: str) -> None:
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: tmp_path / harness)
    monkeypatch.chdir(tmp_path)

    run_chat_server(
        harness=harness,
        port=8900,
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
            uvicorn_run=lambda *_args, **_kwargs: None,
            stdout=StringIO(),
        )


def test_chat_cli_no_headless_warns_and_writes_server_discovery(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr("meridian.cli.chat_cmd.get_user_home", lambda: runtime_root)
    monkeypatch.chdir(tmp_path)
    stdout = StringIO()

    actual_port = run_chat_server(
        host="0.0.0.0",
        port=8765,
        headless=False,
        uvicorn_run=lambda *_args, **_kwargs: None,
        stdout=stdout,
    )

    assert actual_port == 8765
    assert stdout.getvalue().splitlines() == [
        "frontend not yet available, running in headless mode",
        "Chat backend: http://0.0.0.0:8765",
    ]
    discovery = runtime_root / "chat-server.json"
    assert discovery.exists()
    assert '"url": "http://127.0.0.1:8765"' in discovery.read_text(encoding="utf-8")


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
        chat_cmd._chat(harness="opencode", port=8765)
    finally:
        cli_main._GLOBAL_OPTIONS.reset(token)

    assert captured["harness"] == "opencode"


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
    monkeypatch.chdir(tmp_path)

    import meridian.lib.chat.server as chat_server

    monkeypatch.setattr(chat_server, "configure", fake_configure)
    monkeypatch.setattr(chat_server, "app", object())

    run_chat_server(
        harness=harness_name,
        model="model-x",
        port=8900,
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
