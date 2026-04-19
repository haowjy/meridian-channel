"""Process launcher contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class LaunchedProcess:
    """Completed process launch result."""

    exit_code: int
    pid: int | None


class ProcessLauncher(Protocol):
    """Protocol for primary process launch strategies."""

    def launch(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
    ) -> LaunchedProcess: ...


__all__ = ["LaunchedProcess", "ProcessLauncher"]
