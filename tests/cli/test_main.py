from pathlib import Path
import importlib

import pytest

from meridian.lib.launch.types import LaunchResult

main_module = importlib.import_module("meridian.cli.main")


def test_primary_launch_output_formats_resume_hint() -> None:
    payload = main_module.PrimaryLaunchOutput(
        message="Session resumed.",
        exit_code=0,
        lock_path="/tmp/.meridian/active-primary.lock",
        continue_ref="session-2",
        resume_command="meridian --continue session-2",
    )

    assert payload.format_text() == (
        "To continue with meridian:\n"
        "meridian --continue session-2"
    )


def test_run_primary_launch_allows_harness_override_on_continue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        main_module,
        "_resolve_continue_target",
        lambda **_: main_module._ResolvedContinueTarget(
            harness_session_id="session-2",
            harness="claude",
            tracked=False,
            warning="untracked session",
        ),
    )

    def fake_launch_primary(*, repo_root: Path, request: object, harness_registry: object) -> LaunchResult:
        captured["repo_root"] = repo_root
        captured["request"] = request
        captured["registry"] = harness_registry
        return LaunchResult(
            command=("codex", "resume", "session-2"),
            exit_code=0,
            lock_path=repo_root / ".meridian" / "active-primary.json",
            continue_ref="session-2",
        )

    monkeypatch.setattr(main_module, "launch_primary", fake_launch_primary)
    monkeypatch.setattr(main_module, "emit", lambda payload: captured.setdefault("emitted", payload))

    main_module._run_primary_launch(
        continue_ref="session-2",
        model="",
        harness="codex",
        agent=None,
        permission_tier=None,
        approval="confirm",
        yolo=False,
        autocompact=None,
        dry_run=True,
        harness_args=(),
    )

    request = captured["request"]
    assert getattr(request, "harness") == "codex"
    assert getattr(request, "continue_harness_session_id") == "session-2"
