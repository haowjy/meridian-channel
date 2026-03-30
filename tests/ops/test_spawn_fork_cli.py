from pathlib import Path

import pytest

import meridian.cli.spawn as spawn_cli
from meridian.lib.ops.reference import ResolvedSessionReference
from meridian.lib.ops.spawn.models import SpawnActionOutput, SpawnContinueInput, SpawnCreateInput


def _stub_runtime_root(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    monkeypatch.setattr(
        spawn_cli,
        "resolve_runtime_root_and_config",
        lambda _repo_root: (repo_root, object()),
    )


def _stub_output_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spawn_cli, "current_output_sink", lambda: None)


def test_spawn_create_fork_inherits_source_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _stub_runtime_root(monkeypatch, repo_root)
    _stub_output_sink(monkeypatch)

    monkeypatch.setattr(
        spawn_cli,
        "resolve_session_reference",
        lambda _repo_root, _ref: ResolvedSessionReference(
            harness_session_id="session-42",
            harness="claude",
            source_chat_id="c42",
            source_model="gpt-source",
            source_agent="implementer",
            source_skills=("skill-a", "skill-b"),
            source_work_id="w-source",
            tracked=True,
        ),
    )

    captured_input: SpawnCreateInput | None = None

    def _fake_spawn_create_sync(
        payload: SpawnCreateInput,
        ctx=None,
        *,
        sink=None,
    ) -> SpawnActionOutput:
        _ = (ctx, sink)
        nonlocal captured_input
        captured_input = payload
        return SpawnActionOutput(command="spawn.create", status="dry-run")

    monkeypatch.setattr(spawn_cli, "spawn_create_sync", _fake_spawn_create_sync)

    emitted: list[SpawnActionOutput] = []
    spawn_cli._spawn_create(
        emitted.append,
        prompt="forked prompt",
        fork_from="p42",
    )

    assert emitted[0].status == "dry-run"
    assert captured_input is not None
    assert captured_input.model == "gpt-source"
    assert captured_input.agent == "implementer"
    assert captured_input.skills == ("skill-a", "skill-b")
    assert captured_input.work == "w-source"
    assert captured_input.harness == "claude"
    assert captured_input.continue_harness_session_id == "session-42"
    assert captured_input.continue_harness == "claude"
    assert captured_input.continue_source_tracked is True
    assert captured_input.continue_source_ref == "p42"
    assert captured_input.continue_fork is True
    assert captured_input.forked_from_chat_id == "c42"


def test_spawn_create_fork_cli_overrides_take_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _stub_runtime_root(monkeypatch, repo_root)
    _stub_output_sink(monkeypatch)

    monkeypatch.setattr(
        spawn_cli,
        "resolve_session_reference",
        lambda _repo_root, _ref: ResolvedSessionReference(
            harness_session_id="session-42",
            harness="claude",
            source_chat_id="c42",
            source_model="gpt-source",
            source_agent="implementer",
            source_skills=("skill-a", "skill-b"),
            source_work_id="w-source",
            tracked=True,
        ),
    )

    captured_input: SpawnCreateInput | None = None

    def _fake_spawn_create_sync(
        payload: SpawnCreateInput,
        ctx=None,
        *,
        sink=None,
    ) -> SpawnActionOutput:
        _ = (ctx, sink)
        nonlocal captured_input
        captured_input = payload
        return SpawnActionOutput(command="spawn.create", status="dry-run")

    monkeypatch.setattr(spawn_cli, "spawn_create_sync", _fake_spawn_create_sync)

    emitted: list[SpawnActionOutput] = []
    spawn_cli._spawn_create(
        emitted.append,
        prompt="forked prompt",
        fork_from="p42",
        model="gpt-override",
        agent="reviewer",
        work="w-override",
        harness="claude",
    )

    assert emitted[0].status == "dry-run"
    assert captured_input is not None
    assert captured_input.model == "gpt-override"
    assert captured_input.agent == "reviewer"
    assert captured_input.skills == ()
    assert captured_input.work == "w-override"


def test_spawn_create_fork_rejects_cross_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _stub_runtime_root(monkeypatch, repo_root)
    _stub_output_sink(monkeypatch)

    monkeypatch.setattr(
        spawn_cli,
        "resolve_session_reference",
        lambda _repo_root, _ref: ResolvedSessionReference(
            harness_session_id="session-42",
            harness="claude",
            source_chat_id="c42",
            source_model="gpt-source",
            source_agent="implementer",
            source_skills=("skill-a", "skill-b"),
            source_work_id="w-source",
            tracked=True,
        ),
    )

    with pytest.raises(
        ValueError,
        match="Cannot fork across harnesses: source is 'claude', target is 'codex'\\.",
    ):
        spawn_cli._spawn_create(
            lambda _payload: None,
            prompt="forked prompt",
            fork_from="p42",
            harness="codex",
        )


def test_spawn_create_fork_rejects_conflicting_flags() -> None:
    with pytest.raises(ValueError, match="Cannot combine --fork with --continue\\."):
        spawn_cli._spawn_create(
            lambda _payload: None,
            prompt="forked prompt",
            continue_from="p1",
            fork_from="p2",
        )

    with pytest.raises(
        ValueError,
        match="Cannot combine --fork with --from \\(MVP limitation\\)\\.",
    ):
        spawn_cli._spawn_create(
            lambda _payload: None,
            prompt="forked prompt",
            fork_from="p2",
            context_from=("p1",),
        )


def test_spawn_create_continue_path_still_uses_spawn_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_output_sink(monkeypatch)

    captured_input: SpawnContinueInput | None = None

    def _fake_spawn_continue_sync(
        payload: SpawnContinueInput,
        ctx=None,
        *,
        sink=None,
    ) -> SpawnActionOutput:
        _ = (ctx, sink)
        nonlocal captured_input
        captured_input = payload
        return SpawnActionOutput(command="spawn.continue", status="dry-run")

    monkeypatch.setattr(spawn_cli, "spawn_continue_sync", _fake_spawn_continue_sync)

    emitted: list[SpawnActionOutput] = []
    spawn_cli._spawn_create(
        emitted.append,
        continue_from="p12",
        prompt="continue prompt",
    )

    assert emitted[0].status == "dry-run"
    assert captured_input is not None
    assert captured_input.spawn_id == "p12"
    assert captured_input.prompt == "continue prompt"
    assert captured_input.fork is False
