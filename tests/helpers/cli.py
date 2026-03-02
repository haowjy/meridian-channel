"""CLI test runner helper."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def spawn_cli(
    *,
    package_root: Path,
    args: list[str],
    repo_root: Path | None = None,
    cli_env: dict[str, str] | None = None,
    timeout: float = 20.0,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `python -m meridian` with consistent env bootstrapping for tests."""

    env = os.environ.copy()
    if cli_env is not None:
        env.update(cli_env)

    src = str(package_root / "src")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src if not existing_pythonpath else f"{src}:{existing_pythonpath}"

    if repo_root is not None:
        env["MERIDIAN_REPO_ROOT"] = repo_root.as_posix()
    if (
        "spawn" in args
        and "--space" not in args
        and "--space-id" not in args
        and "MERIDIAN_SPACE_ID" not in env
    ):
        env["MERIDIAN_SPACE_ID"] = "s1"

    return subprocess.run(
        [sys.executable, "-m", "meridian", *args],
        cwd=cwd or package_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
