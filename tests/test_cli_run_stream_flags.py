"""CLI run.create streaming flag plumbing tests."""

from __future__ import annotations

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
    assert emitted[0].status == "dry-run"
