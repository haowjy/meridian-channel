import importlib
import json
import subprocess
from pathlib import Path

import pytest

cli_main = importlib.import_module("meridian.cli.main")
mars_ops = importlib.import_module("meridian.lib.ops.mars")


def test_resolve_mars_executable_prefers_current_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scripts_dir = tmp_path / "bin"
    scripts_dir.mkdir()
    (scripts_dir / "mars").write_text("", encoding="utf-8")
    monkeypatch.setattr(mars_ops.sys, "executable", str(scripts_dir / "python"))
    monkeypatch.setattr(mars_ops.shutil, "which", lambda *_args, **_kwargs: "/usr/bin/mars")

    resolved = cli_main._resolve_mars_executable()

    assert resolved == str(scripts_dir / "mars")


def test_resolve_mars_executable_falls_back_to_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scripts_dir = tmp_path / "bin"
    scripts_dir.mkdir()
    monkeypatch.setattr(mars_ops.sys, "executable", str(scripts_dir / "python"))
    monkeypatch.setattr(mars_ops.shutil, "which", lambda *_args, **_kwargs: "/usr/bin/mars")

    resolved = cli_main._resolve_mars_executable()

    assert resolved == "/usr/bin/mars"


def test_resolve_mars_executable_uses_symlink_parent_not_resolved_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool_bin = tmp_path / "tool-bin"
    real_bin = tmp_path / "real-bin"
    tool_bin.mkdir()
    real_bin.mkdir()
    (tool_bin / "mars").write_text("", encoding="utf-8")
    (tool_bin / "python3").symlink_to(real_bin / "python3")

    monkeypatch.setattr(mars_ops.sys, "executable", str(tool_bin / "python3"))
    monkeypatch.setattr(mars_ops.shutil, "which", lambda *_args, **_kwargs: "/usr/bin/mars")

    resolved = cli_main._resolve_mars_executable()

    assert resolved == str(tool_bin / "mars")


def test_run_mars_passthrough_sync_prints_upgrade_hint_in_text_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_main, "_resolve_mars_executable", lambda: "/usr/bin/mars")
    monkeypatch.setattr(
        cli_main,
        "check_upgrade_availability",
        lambda *_args, **_kwargs: mars_ops.UpgradeAvailability(
            count=2,
            names=("meridian-base", "meridian-dev-workflow"),
        ),
    )

    def _fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert "capture_output" not in kwargs
        assert "text" not in kwargs
        print("sync output")
        return subprocess.CompletedProcess(
            args=["/usr/bin/mars", "sync"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli_main.subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_main._run_mars_passthrough(["sync"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "sync output\n" in captured.out
    assert "hint: 2 updates available (meridian-base, meridian-dev-workflow)." in captured.out
    assert (
        "Run `meridian mars outdated` to see details, or `meridian mars upgrade` to apply."
        in captured.out
    )


def test_run_mars_passthrough_sync_injects_upgrade_hint_in_json_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_main, "_resolve_mars_executable", lambda: "/usr/bin/mars")
    monkeypatch.setattr(
        cli_main,
        "check_upgrade_availability",
        lambda *_args, **_kwargs: mars_ops.UpgradeAvailability(
            count=1,
            names=("meridian-base",),
        ),
    )
    commands: list[list[str]] = []
    run_kwargs: list[dict[str, object]] = []

    def _fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        run_kwargs.append(dict(_kwargs))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"ok": true, "installed": 0}\n',
            stderr="",
        )

    monkeypatch.setattr(cli_main.subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_main._run_mars_passthrough(["sync"], output_format="json")

    assert exc_info.value.code == 0
    assert commands and "--json" in commands[0]
    assert run_kwargs and run_kwargs[0].get("capture_output") is True
    assert run_kwargs[0].get("text") is True
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["upgrade_hint"] == {
        "count": 1,
        "names": ["meridian-base"],
    }


def test_run_mars_passthrough_sync_stays_silent_when_upgrade_check_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_main, "_resolve_mars_executable", lambda: "/usr/bin/mars")
    monkeypatch.setattr(
        cli_main,
        "check_upgrade_availability",
        lambda *_args, **_kwargs: None,
    )

    def _fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        print("sync output")
        return subprocess.CompletedProcess(
            args=["/usr/bin/mars", "sync"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli_main.subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_main._run_mars_passthrough(["sync"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == "sync output\n"


def test_main_mars_defaults_to_json_in_agent_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERIDIAN_DEPTH", "1")
    monkeypatch.setattr(cli_main, "_interactive_terminal_attached", lambda: False)
    captured: dict[str, object] = {}

    def _fake_passthrough(args: object, *, output_format: str | None = None) -> None:
        captured["args"] = args
        captured["output_format"] = output_format
        raise SystemExit(0)

    monkeypatch.setattr(cli_main, "_run_mars_passthrough", _fake_passthrough)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["mars", "sync"])

    assert exc_info.value.code == 0
    assert captured["args"] == ["sync"]
    assert captured["output_format"] == "json"


def test_run_mars_passthrough_list_honors_json_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_main, "_resolve_mars_executable", lambda: "/usr/bin/mars")
    commands: list[list[str]] = []
    run_kwargs: list[dict[str, object]] = []

    def _fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        run_kwargs.append(dict(_kwargs))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"packages": []}\n',
            stderr="",
        )

    monkeypatch.setattr(cli_main.subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_main._run_mars_passthrough(["list"], output_format="json")

    assert exc_info.value.code == 0
    assert commands and commands[0] == ["/usr/bin/mars", "--json", "list"]
    assert run_kwargs and run_kwargs[0].get("capture_output") is True
    assert run_kwargs[0].get("text") is True
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {"packages": []}


def test_agent_mode_mars_list_emits_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MERIDIAN_DEPTH", "1")
    monkeypatch.setattr(cli_main, "_interactive_terminal_attached", lambda: False)
    monkeypatch.setattr(cli_main, "_resolve_mars_executable", lambda: "/usr/bin/mars")
    commands: list[list[str]] = []
    run_kwargs: list[dict[str, object]] = []

    def _fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        run_kwargs.append(dict(_kwargs))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"packages": []}\n',
            stderr="",
        )

    monkeypatch.setattr(cli_main.subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["mars", "list"])

    assert exc_info.value.code == 0
    assert commands and commands[0] == ["/usr/bin/mars", "--json", "list"]
    assert run_kwargs and run_kwargs[0].get("capture_output") is True
    assert run_kwargs[0].get("text") is True
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {"packages": []}
