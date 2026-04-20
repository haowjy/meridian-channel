"""Built-in git autosync hook implementation."""

from __future__ import annotations

import fnmatch
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

import structlog

from meridian.lib.hooks.types import Hook, HookContext, HookOutcome, HookResult

logger = structlog.get_logger(__name__)

_REQUIREMENTS_TIMEOUT_SECS = 5
_PULL_TIMEOUT_SECS = 60
_ADD_TIMEOUT_SECS = 30
_COMMIT_TIMEOUT_SECS = 30
_PUSH_TIMEOUT_SECS = 60
_REBASE_ABORT_TIMEOUT_SECS = 30
_DIFF_TIMEOUT_SECS = 30
_MAX_ERROR_CHARS = 500
_REBASE_CONFLICT_MARKERS = (
    "conflict",
    "resolve all conflicts manually",
    "could not apply",
)


@dataclass(frozen=True)
class _SyncOutcome:
    outcome: HookOutcome
    success: bool
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None


class GitAutosync:
    """Automatically sync a work directory to its git remote."""

    name: str = "git-autosync"
    requirements: tuple[str, ...] = ("git",)
    default_events: tuple[str, ...] = ("spawn.finalized", "work.done")
    default_interval: str | None = "10m"

    def check_requirements(self) -> tuple[bool, str | None]:
        """Return whether git is available in the environment."""

        git_bin = shutil.which("git")
        if git_bin is None:
            return False, "git CLI not found in PATH."

        try:
            result = subprocess.run(
                [git_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=_REQUIREMENTS_TIMEOUT_SECS,
                check=False,
            )
        except FileNotFoundError:
            return False, "git CLI not found in PATH."
        except subprocess.TimeoutExpired:
            return False, "git --version timed out."
        except OSError as exc:
            return False, f"git --version failed: {exc}"

        if result.returncode != 0:
            return False, "git --version returned a non-zero exit code."
        return True, None

    def execute(self, context: HookContext, config: Hook) -> HookResult:
        """Execute git autosync for one hook invocation."""

        start = time.monotonic()
        work_dir = context.work_dir
        if not work_dir:
            return self._result(
                config,
                context,
                _SyncOutcome(
                    outcome="skipped",
                    success=True,
                    skipped=True,
                    skip_reason="missing_work_dir",
                    error="Hook context does not include work_dir.",
                ),
                start=start,
            )

        try:
            is_repo, repo_error = self._is_git_repository(work_dir)
            if not is_repo:
                logger.warning(
                    "git_autosync_repo_not_eligible",
                    work_dir=work_dir,
                    error=repo_error,
                )
                return self._result(
                    config,
                    context,
                    _SyncOutcome(
                        outcome="skipped",
                        success=True,
                        skipped=True,
                        skip_reason="not_git_repository",
                        error=repo_error,
                    ),
                    start=start,
                )

            outcome = self._sync(work_dir, config.exclude)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning(
                "git_autosync_runtime_error",
                work_dir=work_dir,
                error=str(exc),
            )
            outcome = _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="git_runtime_error",
                error=str(exc),
            )
        return self._result(config, context, outcome, start=start)

    def _sync(self, work_dir: str, excludes: tuple[str, ...]) -> _SyncOutcome:
        pull = self._run_git(
            work_dir,
            ["pull", "--rebase", "--autostash"],
            timeout=_PULL_TIMEOUT_SECS,
        )
        if pull.returncode != 0:
            message = self._format_git_error("git pull --rebase failed", pull)
            if self._is_rebase_conflict(pull):
                abort = self._run_git(
                    work_dir,
                    ["rebase", "--abort"],
                    timeout=_REBASE_ABORT_TIMEOUT_SECS,
                )
                logger.warning(
                    "git_autosync_rebase_conflict",
                    work_dir=work_dir,
                    pull_error=message,
                    abort_return_code=abort.returncode,
                )
                return _SyncOutcome(
                    outcome="skipped",
                    success=True,
                    skipped=True,
                    skip_reason="rebase_conflict",
                    error=message,
                )

            logger.warning("git_autosync_pull_failed", work_dir=work_dir, error=message)
            return _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="pull_failed",
                error=message,
            )

        add = self._run_git(work_dir, ["add", "-A"], timeout=_ADD_TIMEOUT_SECS)
        if add.returncode != 0:
            message = self._format_git_error("git add -A failed", add)
            logger.warning("git_autosync_add_failed", work_dir=work_dir, error=message)
            return _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="add_failed",
                error=message,
            )

        if excludes:
            excluded_paths_result = self._run_git(
                work_dir,
                ["diff", "--cached", "--name-only", "-z"],
                timeout=_DIFF_TIMEOUT_SECS,
            )
            if excluded_paths_result.returncode != 0:
                message = self._format_git_error(
                    "git diff --cached --name-only failed",
                    excluded_paths_result,
                )
                logger.warning(
                    "git_autosync_exclude_scan_failed",
                    work_dir=work_dir,
                    error=message,
                )
                return _SyncOutcome(
                    outcome="skipped",
                    success=True,
                    skipped=True,
                    skip_reason="exclude_scan_failed",
                    error=message,
                )

            staged_paths = self._parse_nul_paths(excluded_paths_result.stdout)
            excluded_paths = [
                path for path in staged_paths if self._is_excluded_path(path, excludes)
            ]
            if excluded_paths:
                reset = self._run_git(
                    work_dir,
                    ["reset", "--quiet", "--", *excluded_paths],
                    timeout=_ADD_TIMEOUT_SECS,
                )
                if reset.returncode != 0:
                    message = self._format_git_error("git reset excluded paths failed", reset)
                    logger.warning(
                        "git_autosync_exclude_reset_failed",
                        work_dir=work_dir,
                        error=message,
                    )
                    return _SyncOutcome(
                        outcome="skipped",
                        success=True,
                        skipped=True,
                        skip_reason="exclude_reset_failed",
                        error=message,
                    )

        staged_check = self._run_git(
            work_dir,
            ["diff", "--cached", "--quiet"],
            timeout=_DIFF_TIMEOUT_SECS,
        )
        if staged_check.returncode == 0:
            return _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="nothing_to_commit",
            )
        if staged_check.returncode != 1:
            message = self._format_git_error("git diff --cached --quiet failed", staged_check)
            logger.warning("git_autosync_staged_check_failed", work_dir=work_dir, error=message)
            return _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="staged_check_failed",
                error=message,
            )

        commit_message = f"autosync: {datetime.now(UTC).isoformat()}"
        commit = self._run_git(
            work_dir,
            ["commit", "-m", commit_message],
            timeout=_COMMIT_TIMEOUT_SECS,
        )
        if commit.returncode != 0:
            if self._looks_like_nothing_to_commit(commit):
                return _SyncOutcome(
                    outcome="skipped",
                    success=True,
                    skipped=True,
                    skip_reason="nothing_to_commit",
                )

            message = self._format_git_error("git commit failed", commit)
            logger.warning("git_autosync_commit_failed", work_dir=work_dir, error=message)
            return _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="commit_failed",
                error=message,
            )

        push = self._run_git(work_dir, ["push"], timeout=_PUSH_TIMEOUT_SECS)
        if push.returncode != 0:
            message = self._format_git_error("git push failed", push)
            logger.warning("git_autosync_push_failed", work_dir=work_dir, error=message)
            return _SyncOutcome(
                outcome="skipped",
                success=True,
                skipped=True,
                skip_reason="push_failed",
                error=message,
            )

        return _SyncOutcome(outcome="success", success=True)

    def _is_git_repository(self, work_dir: str) -> tuple[bool, str | None]:
        check = self._run_git(
            work_dir,
            ["rev-parse", "--is-inside-work-tree"],
            timeout=_REQUIREMENTS_TIMEOUT_SECS,
        )
        if check.returncode != 0:
            return False, self._format_git_error("Not a git repository", check)
        return check.stdout.strip().lower() == "true", None

    def _run_git(
        self,
        work_dir: str,
        args: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _result(
        self,
        config: Hook,
        context: HookContext,
        outcome: _SyncOutcome,
        *,
        start: float,
    ) -> HookResult:
        return HookResult(
            hook_name=config.name,
            event=context.event_name,
            outcome=outcome.outcome,
            success=outcome.success,
            skipped=outcome.skipped,
            skip_reason=outcome.skip_reason,
            error=outcome.error,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    def _format_git_error(
        self,
        prefix: str,
        result: subprocess.CompletedProcess[str],
    ) -> str:
        details = (result.stderr or result.stdout or "").strip()
        if details:
            return f"{prefix}: {details[:_MAX_ERROR_CHARS]}"
        return f"{prefix}: exit {result.returncode}"

    def _is_rebase_conflict(self, result: subprocess.CompletedProcess[str]) -> bool:
        haystack = f"{result.stdout}\n{result.stderr}".lower()
        return any(marker in haystack for marker in _REBASE_CONFLICT_MARKERS)

    def _looks_like_nothing_to_commit(self, result: subprocess.CompletedProcess[str]) -> bool:
        haystack = f"{result.stdout}\n{result.stderr}".lower()
        return "nothing to commit" in haystack or "no changes added to commit" in haystack

    def _parse_nul_paths(self, raw: str) -> tuple[str, ...]:
        if not raw:
            return ()
        return tuple(path for path in raw.split("\0") if path)

    def _is_excluded_path(self, path: str, excludes: tuple[str, ...]) -> bool:
        posix_path = path.replace("\\", "/")
        basename = PurePosixPath(posix_path).name
        for pattern in excludes:
            normalized_pattern = pattern.replace("\\", "/").strip()
            if not normalized_pattern:
                continue

            if normalized_pattern.endswith("/"):
                prefix = normalized_pattern.rstrip("/")
                if posix_path == prefix or posix_path.startswith(f"{prefix}/"):
                    return True
                continue

            if fnmatch.fnmatch(posix_path, normalized_pattern):
                return True
            if "/" not in normalized_pattern and fnmatch.fnmatch(basename, normalized_pattern):
                return True
        return False


GIT_AUTOSYNC = GitAutosync()

__all__ = ["GIT_AUTOSYNC", "GitAutosync"]
