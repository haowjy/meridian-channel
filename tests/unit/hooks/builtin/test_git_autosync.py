from __future__ import annotations

import subprocess
from unittest.mock import ANY
from uuid import uuid4

from meridian.lib.hooks.builtin.git_autosync import GIT_AUTOSYNC
from meridian.lib.hooks.types import Hook, HookContext


def _hook(*, exclude: tuple[str, ...] = ()) -> Hook:
    return Hook(
        name="git-autosync",
        event="work.done",
        source="project",
        builtin="git-autosync",
        exclude=exclude,
    )


def _context(work_dir: str | None) -> HookContext:
    return HookContext(
        event_name="work.done",
        event_id=uuid4(),
        timestamp="2026-04-20T00:00:00+00:00",
        repo_root="/repo",
        state_root="/repo/.meridian",
        work_id="w123",
        work_dir=work_dir,
    )


def _cp(
    *,
    args: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_git_autosync_declares_metadata() -> None:
    assert GIT_AUTOSYNC.name == "git-autosync"
    assert GIT_AUTOSYNC.requirements == ("git",)
    assert GIT_AUTOSYNC.default_events == ("spawn.finalized", "work.done")
    assert GIT_AUTOSYNC.default_interval == "10m"


def test_check_requirements_returns_false_when_git_missing(monkeypatch) -> None:
    monkeypatch.setattr("meridian.lib.hooks.builtin.git_autosync.shutil.which", lambda _: None)

    ok, error = GIT_AUTOSYNC.check_requirements()

    assert ok is False
    assert error == "git CLI not found in PATH."


def test_execute_skips_when_work_dir_missing() -> None:
    result = GIT_AUTOSYNC.execute(_context(None), _hook())

    assert result.outcome == "skipped"
    assert result.success is True
    assert result.skipped is True
    assert result.skip_reason == "missing_work_dir"


def test_execute_skips_when_work_dir_is_not_git_repo(monkeypatch) -> None:
    monkeypatch.setattr(
        GIT_AUTOSYNC,
        "_run_git",
        lambda work_dir, args, timeout: _cp(
            args=["git", *args],
            returncode=128,
            stderr="fatal: not a git repository",
        ),
    )

    result = GIT_AUTOSYNC.execute(_context("/tmp/work"), _hook())

    assert result.outcome == "skipped"
    assert result.success is True
    assert result.skipped is True
    assert result.skip_reason == "not_git_repository"


def test_execute_runs_sync_sequence_and_pushes(monkeypatch) -> None:
    calls: list[list[str]] = []
    responses = iter(
        [
            _cp(args=["git", "rev-parse", "--is-inside-work-tree"], stdout="true\n"),
            _cp(args=["git", "pull", "--rebase", "--autostash"]),
            _cp(args=["git", "add", "-A"]),
            _cp(args=["git", "diff", "--cached", "--quiet"], returncode=1),
            _cp(args=["git", "commit", "-m", "autosync: now"]),
            _cp(args=["git", "push"]),
        ]
    )

    def fake_run_git(
        work_dir: str,
        args: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        _ = work_dir, timeout
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(GIT_AUTOSYNC, "_run_git", fake_run_git)

    result = GIT_AUTOSYNC.execute(_context("/tmp/work"), _hook())

    assert result.outcome == "success"
    assert result.success is True
    assert result.skipped is False
    assert calls == [
        ["rev-parse", "--is-inside-work-tree"],
        ["pull", "--rebase", "--autostash"],
        ["add", "-A"],
        ["diff", "--cached", "--quiet"],
        ["commit", "-m", ANY],
        ["push"],
    ]


def test_execute_aborts_rebase_and_skips_on_conflict(monkeypatch) -> None:
    calls: list[list[str]] = []
    responses = iter(
        [
            _cp(args=["git", "rev-parse", "--is-inside-work-tree"], stdout="true\n"),
            _cp(
                args=["git", "pull", "--rebase", "--autostash"],
                returncode=1,
                stderr="CONFLICT (content): Merge conflict in shared.txt",
            ),
            _cp(args=["git", "rebase", "--abort"]),
        ]
    )

    def fake_run_git(
        work_dir: str,
        args: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        _ = work_dir, timeout
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(GIT_AUTOSYNC, "_run_git", fake_run_git)

    result = GIT_AUTOSYNC.execute(_context("/tmp/work"), _hook())

    assert result.outcome == "skipped"
    assert result.success is True
    assert result.skip_reason == "rebase_conflict"
    assert calls == [
        ["rev-parse", "--is-inside-work-tree"],
        ["pull", "--rebase", "--autostash"],
        ["rebase", "--abort"],
    ]


def test_execute_skips_push_when_nothing_to_commit(monkeypatch) -> None:
    calls: list[list[str]] = []
    responses = iter(
        [
            _cp(args=["git", "rev-parse", "--is-inside-work-tree"], stdout="true\n"),
            _cp(args=["git", "pull", "--rebase", "--autostash"]),
            _cp(args=["git", "add", "-A"]),
            _cp(args=["git", "diff", "--cached", "--quiet"], returncode=0),
        ]
    )

    def fake_run_git(
        work_dir: str,
        args: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        _ = work_dir, timeout
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(GIT_AUTOSYNC, "_run_git", fake_run_git)

    result = GIT_AUTOSYNC.execute(_context("/tmp/work"), _hook())

    assert result.outcome == "skipped"
    assert result.success is True
    assert result.skip_reason == "nothing_to_commit"
    assert calls == [
        ["rev-parse", "--is-inside-work-tree"],
        ["pull", "--rebase", "--autostash"],
        ["add", "-A"],
        ["diff", "--cached", "--quiet"],
    ]


def test_execute_applies_exclude_patterns_before_commit(monkeypatch) -> None:
    calls: list[list[str]] = []
    responses = iter(
        [
            _cp(args=["git", "rev-parse", "--is-inside-work-tree"], stdout="true\n"),
            _cp(args=["git", "pull", "--rebase", "--autostash"]),
            _cp(args=["git", "add", "-A"]),
            _cp(
                args=["git", "diff", "--cached", "--name-only", "-z"],
                stdout="keep.txt\0debug.log\0tmp/cache.txt\0",
            ),
            _cp(args=["git", "reset", "--quiet", "--", "debug.log", "tmp/cache.txt"]),
            _cp(args=["git", "diff", "--cached", "--quiet"], returncode=1),
            _cp(args=["git", "commit", "-m", "autosync: now"]),
            _cp(args=["git", "push"]),
        ]
    )

    def fake_run_git(
        work_dir: str,
        args: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        _ = work_dir, timeout
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(GIT_AUTOSYNC, "_run_git", fake_run_git)

    result = GIT_AUTOSYNC.execute(
        _context("/tmp/work"),
        _hook(exclude=("*.log", "tmp/")),
    )

    assert result.outcome == "success"
    assert result.success is True
    assert ["reset", "--quiet", "--", "debug.log", "tmp/cache.txt"] in calls


def test_execute_treats_push_failure_as_fail_open_skip(monkeypatch) -> None:
    responses = iter(
        [
            _cp(args=["git", "rev-parse", "--is-inside-work-tree"], stdout="true\n"),
            _cp(args=["git", "pull", "--rebase", "--autostash"]),
            _cp(args=["git", "add", "-A"]),
            _cp(args=["git", "diff", "--cached", "--quiet"], returncode=1),
            _cp(args=["git", "commit", "-m", "autosync: now"]),
            _cp(args=["git", "push"], returncode=1, stderr="fatal: Authentication failed"),
        ]
    )

    monkeypatch.setattr(
        GIT_AUTOSYNC,
        "_run_git",
        lambda work_dir, args, timeout: next(responses),
    )

    result = GIT_AUTOSYNC.execute(_context("/tmp/work"), _hook())

    assert result.outcome == "skipped"
    assert result.success is True
    assert result.skipped is True
    assert result.skip_reason == "push_failed"


def test_is_excluded_path_matches_glob_and_directory_patterns() -> None:
    assert GIT_AUTOSYNC._is_excluded_path("logs/debug.log", ("*.log",)) is True
    assert GIT_AUTOSYNC._is_excluded_path("tmp/output.txt", ("tmp/",)) is True
    assert GIT_AUTOSYNC._is_excluded_path("src/main.py", ("tmp/", "*.log")) is False


def test_parse_nul_paths_handles_empty_and_normalized_content() -> None:
    assert GIT_AUTOSYNC._parse_nul_paths("") == ()
    assert GIT_AUTOSYNC._parse_nul_paths("a\0b\0") == ("a", "b")
