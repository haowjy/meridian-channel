"""Unit tests for local (non-app-server) ext run dispatch."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import meridian.cli.ext_cmd as ext_cmd
from meridian.cli.ext_cmd import ext_run
from meridian.lib.extensions.context import (
    ExtensionCommandServices,
    ExtensionInvocationContext,
)
from meridian.lib.extensions.types import ExtensionJSONResult, ExtensionSurface


@pytest.fixture(autouse=True)
def _reset_ext_output_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ext_cmd, "_emit", None)
    monkeypatch.setattr(ext_cmd, "_resolve_global_format", None)


class _RecordingDispatcher:
    def __init__(self, result: object) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    async def dispatch(
        self,
        fqid: str,
        args: dict[str, object],
        context: ExtensionInvocationContext,
        services: ExtensionCommandServices,
    ) -> object:
        self.calls.append(
            {
                "fqid": fqid,
                "args": args,
                "context": context,
                "services": services,
            }
        )
        return self._result


def test_ext_run_local_command_dispatches_without_app_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SimpleNamespace(
        fqid="demo.echo",
        extension_id="demo",
        command_id="echo",
        surfaces=frozenset({ExtensionSurface.CLI}),
        requires_app_server=False,
    )
    dispatcher = _RecordingDispatcher(ExtensionJSONResult(payload={"answer": 42}))

    class _FakeRegistry:
        def get(self, fqid: str) -> SimpleNamespace | None:
            if fqid == spec.fqid:
                return spec
            return None

    monkeypatch.setattr(ext_cmd, "build_first_party_registry", lambda: _FakeRegistry())
    monkeypatch.setattr(ext_cmd, "ExtensionCommandDispatcher", lambda _registry: dispatcher)

    class _UnexpectedLocator:
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover
            _ = (args, kwargs)
            raise AssertionError("AppServerLocator must not be used for local commands")

    monkeypatch.setattr(ext_cmd, "AppServerLocator", _UnexpectedLocator)

    ext_run(
        "demo.echo",
        args='{"name":"Meridian"}',
        request_id="req-1",
        work_id="work-1",
        spawn_id="spawn-1",
        json_output=True,
    )

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"result": {"answer": 42}}
    assert captured.err == ""

    assert len(dispatcher.calls) == 1
    call = dispatcher.calls[0]
    context = call["context"]
    assert isinstance(context, ExtensionInvocationContext)
    assert call["fqid"] == spec.fqid
    assert call["args"] == {"name": "Meridian"}
    assert isinstance(call["services"], ExtensionCommandServices)
    assert context.caller_surface == ExtensionSurface.CLI
    assert context.request_id == "req-1"
    assert context.work_id == "work-1"
    assert context.spawn_id == "spawn-1"
