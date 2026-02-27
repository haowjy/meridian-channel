"""CLI run.create streaming flag plumbing tests."""

from __future__ import annotations

import pytest

from meridian.cli import run as run_cli
from meridian.lib.ops.run import RunActionOutput, RunCreateInput


def test_run_create_passes_verbose_and_quiet_flags(
    monkeypatch,
) -> None:
    captured: dict[str, RunCreateInput] = {}
    emitted: list[RunActionOutput] = []

    def fake_run_create_sync(payload: RunCreateInput) -> RunActionOutput:
        captured["payload"] = payload
        return RunActionOutput(command="run.create", status="dry-run")

    monkeypatch.setattr(run_cli, "run_create_sync", fake_run_create_sync)
    run_cli._run_create(
        emitted.append,
        prompt="test",
        dry_run=True,
        verbose=True,
        quiet=True,
    )

    payload = captured["payload"]
    assert payload.verbose is True
    assert payload.quiet is True
    assert payload.stream is False
    assert emitted[0].status == "dry-run"


def test_run_create_passes_stream_flag(monkeypatch) -> None:
    captured: dict[str, RunCreateInput] = {}
    emitted: list[RunActionOutput] = []

    def fake_run_create_sync(payload: RunCreateInput) -> RunActionOutput:
        captured["payload"] = payload
        return RunActionOutput(command="run.create", status="dry-run")

    monkeypatch.setattr(run_cli, "run_create_sync", fake_run_create_sync)
    run_cli._run_create(
        emitted.append,
        prompt="test",
        dry_run=True,
        stream=True,
    )

    payload = captured["payload"]
    assert payload.stream is True
    assert payload.verbose is False
    assert payload.quiet is False
    assert payload.background is False
    assert emitted[0].status == "dry-run"


def test_run_create_passes_background_flag(monkeypatch) -> None:
    captured: dict[str, RunCreateInput] = {}
    emitted: list[RunActionOutput] = []

    def fake_run_create_sync(payload: RunCreateInput) -> RunActionOutput:
        captured["payload"] = payload
        return RunActionOutput(command="run.create", status="running", run_id="r1")

    monkeypatch.setattr(run_cli, "run_create_sync", fake_run_create_sync)
    run_cli._run_create(
        emitted.append,
        prompt="test",
        background=True,
    )

    payload = captured["payload"]
    assert payload.background is True
    assert emitted[0].status == "running"


def test_run_create_propagates_failed_run_exit_code(monkeypatch) -> None:
    def fake_run_create_sync(payload: RunCreateInput) -> RunActionOutput:
        _ = payload
        return RunActionOutput(command="run.create", status="failed", exit_code=7)

    monkeypatch.setattr(run_cli, "run_create_sync", fake_run_create_sync)

    with pytest.raises(SystemExit) as exc_info:
        run_cli._run_create(
            lambda _: None,
            prompt="test",
        )

    assert int(exc_info.value.code) == 7


def test_run_create_uses_nonzero_exit_for_failed_result_without_exit_code(monkeypatch) -> None:
    def fake_run_create_sync(payload: RunCreateInput) -> RunActionOutput:
        _ = payload
        return RunActionOutput(command="run.create", status="failed")

    monkeypatch.setattr(run_cli, "run_create_sync", fake_run_create_sync)

    with pytest.raises(SystemExit) as exc_info:
        run_cli._run_create(
            lambda _: None,
            prompt="test",
        )

    assert int(exc_info.value.code) == 1
