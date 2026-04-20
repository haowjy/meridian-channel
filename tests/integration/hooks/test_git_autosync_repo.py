from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from meridian.lib.hooks.builtin.git_autosync import GitAutosync
from meridian.lib.hooks.types import Hook, HookContext

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git CLI is required")


def _git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        pytest.fail(
            "git command failed: "
            f"{' '.join(args)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _context(work_dir: Path) -> HookContext:
    return HookContext(
        event_name="work.done",
        event_id=uuid4(),
        timestamp="2026-04-20T00:00:00+00:00",
        repo_root=str(work_dir),
        state_root=str(work_dir / ".meridian"),
        work_id="w123",
        work_dir=str(work_dir),
    )


def _hook(*, exclude: tuple[str, ...] = ()) -> Hook:
    return Hook(
        name="git-autosync",
        event="work.done",
        source="project",
        builtin="git-autosync",
        exclude=exclude,
    )


def _init_commit_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", cwd=path)
    _git("config", "user.email", "autosync-test@example.com", cwd=path)
    _git("config", "user.name", "Autosync Test", cwd=path)
    (path / "shared.txt").write_text("seed\n", encoding="utf-8")
    (path / "keep.txt").write_text("seed\n", encoding="utf-8")
    _git("add", "-A", cwd=path)
    _git("commit", "-m", "seed", cwd=path)


def _seed_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    _git("init", "--bare", str(remote))

    seed = tmp_path / "seed"
    _init_commit_repo(seed)
    _git("remote", "add", "origin", str(remote), cwd=seed)
    _git("push", "-u", "origin", "HEAD", cwd=seed)

    work = tmp_path / "work"
    _git("clone", str(remote), str(work))
    _git("config", "user.email", "autosync-test@example.com", cwd=work)
    _git("config", "user.name", "Autosync Test", cwd=work)
    return remote, work


def _current_branch(repo: Path) -> str:
    return _git("branch", "--show-current", cwd=repo).stdout.strip()


def _remote_head(remote: Path, branch: str) -> str:
    return _git("--git-dir", str(remote), "rev-parse", f"refs/heads/{branch}").stdout.strip()


def test_git_autosync_syncs_and_pushes_changes(tmp_path: Path) -> None:
    remote, work = _seed_remote(tmp_path)
    branch = _current_branch(work)
    before_remote = _remote_head(remote, branch)

    (work / "keep.txt").write_text("local change\n", encoding="utf-8")
    (work / "new.txt").write_text("new file\n", encoding="utf-8")

    hook = GitAutosync()
    result = hook.execute(_context(work), _hook())

    assert result.outcome == "success"
    assert result.success is True
    assert result.skipped is False

    subject = _git("log", "-1", "--pretty=%s", cwd=work).stdout.strip()
    assert subject.startswith("autosync: ")

    after_remote = _remote_head(remote, branch)
    assert before_remote != after_remote

    status = _git("status", "--porcelain", cwd=work).stdout
    assert status.strip() == ""


def test_git_autosync_excludes_configured_paths(tmp_path: Path) -> None:
    remote, work = _seed_remote(tmp_path)
    _ = remote
    (work / "keep.txt").write_text("include me\n", encoding="utf-8")
    (work / "debug.log").write_text("exclude me\n", encoding="utf-8")
    (work / "tmp").mkdir()
    (work / "tmp" / "cache.txt").write_text("exclude dir\n", encoding="utf-8")

    hook = GitAutosync()
    result = hook.execute(_context(work), _hook(exclude=("*.log", "tmp/")))

    assert result.outcome == "success"
    assert result.success is True

    changed = _git("show", "--pretty=format:", "--name-only", "HEAD", cwd=work).stdout
    changed_paths = {line.strip() for line in changed.splitlines() if line.strip()}
    assert "keep.txt" in changed_paths
    assert "debug.log" not in changed_paths
    assert "tmp/cache.txt" not in changed_paths

    status_lines = _git("status", "--porcelain", cwd=work).stdout.splitlines()
    assert any("debug.log" in line for line in status_lines)
    assert any("tmp/" in line or "tmp/cache.txt" in line for line in status_lines)


def test_git_autosync_aborts_rebase_conflict_and_skips(tmp_path: Path) -> None:
    remote, work = _seed_remote(tmp_path)
    branch = _current_branch(work)

    other = tmp_path / "other"
    _git("clone", str(remote), str(other))
    _git("config", "user.email", "autosync-test@example.com", cwd=other)
    _git("config", "user.name", "Autosync Test", cwd=other)

    (other / "shared.txt").write_text("remote change\n", encoding="utf-8")
    _git("add", "-A", cwd=other)
    _git("commit", "-m", "remote change", cwd=other)
    _git("push", "origin", "HEAD", cwd=other)
    remote_head_after_other = _remote_head(remote, branch)

    (work / "shared.txt").write_text("local change\n", encoding="utf-8")
    _git("add", "-A", cwd=work)
    _git("commit", "-m", "local change", cwd=work)
    local_head = _git("rev-parse", "HEAD", cwd=work).stdout.strip()

    hook = GitAutosync()
    result = hook.execute(_context(work), _hook())

    assert result.outcome == "skipped"
    assert result.success is True
    assert result.skipped is True
    assert result.skip_reason == "rebase_conflict"

    assert not (work / ".git" / "rebase-merge").exists()
    assert not (work / ".git" / "rebase-apply").exists()

    top_subject = _git("log", "-1", "--pretty=%s", cwd=work).stdout.strip()
    assert top_subject == "local change"

    remote_head_after_hook = _remote_head(remote, branch)
    assert remote_head_after_hook == remote_head_after_other
    assert remote_head_after_hook != local_head
