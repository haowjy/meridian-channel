import importlib

import pytest

cli_main = importlib.import_module("meridian.cli.main")
hooks_cli = importlib.import_module("meridian.cli.hooks_commands")
ops_hooks = importlib.import_module("meridian.lib.ops.hooks")


def test_hooks_group_is_registered() -> None:
    assert "hooks" in cli_main.app.resolved_commands()


def test_hooks_list_routes_through_hooks_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERIDIAN_DEPTH", "1")
    captured: dict[str, object] = {}

    def _fake_hooks_list_sync(payload: ops_hooks.HookListInput) -> ops_hooks.HookListOutput:
        captured["payload"] = payload
        return ops_hooks.HookListOutput(hooks=())

    monkeypatch.setattr(hooks_cli, "hooks_list_sync", _fake_hooks_list_sync)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["hooks", "list"])

    assert exc_info.value.code == 0
    assert isinstance(captured["payload"], ops_hooks.HookListInput)


def test_hooks_run_passes_hook_name_and_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERIDIAN_DEPTH", "1")
    captured: dict[str, object] = {}

    def _fake_hooks_run_sync(payload: ops_hooks.HookRunInput) -> ops_hooks.HookRunOutput:
        captured["payload"] = payload
        return ops_hooks.HookRunOutput(
            hook=payload.name,
            event="spawn.finalized",
            result=ops_hooks.HookRunResult(
                outcome="success",
                success=True,
                skipped=False,
                duration_ms=1,
            ),
        )

    monkeypatch.setattr(hooks_cli, "hooks_run_sync", _fake_hooks_run_sync)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["hooks", "run", "record-finalized", "--event", "work.done"])

    assert exc_info.value.code == 0
    assert isinstance(captured["payload"], ops_hooks.HookRunInput)
    assert captured["payload"].name == "record-finalized"
    assert captured["payload"].event == "work.done"


def test_hooks_check_exits_non_zero_when_requirements_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MERIDIAN_DEPTH", "1")

    def _fake_hooks_check_sync(_payload: ops_hooks.HookCheckInput) -> ops_hooks.HookCheckOutput:
        return ops_hooks.HookCheckOutput(
            ok=False,
            checks=(
                ops_hooks.HookCheckItem(
                    name="git-autosync",
                    ok=False,
                    requirements=("git",),
                    error="git missing",
                ),
            ),
        )

    monkeypatch.setattr(hooks_cli, "hooks_check_sync", _fake_hooks_check_sync)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["hooks", "check"])

    assert exc_info.value.code == 1
