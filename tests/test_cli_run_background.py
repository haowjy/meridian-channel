"""CLI integration checks for run.create --background behavior."""

from __future__ import annotations

import json
import re
from pathlib import Path


def test_run_create_background_prints_run_id_in_text_mode(
    run_meridian,
    cli_env: dict[str, str],
    tmp_path: Path,
) -> None:
    cli_env["MERIDIAN_REPO_ROOT"] = tmp_path.as_posix()

    created = run_meridian(
        [
            "run",
            "--background",
            "--timeout-secs",
            "0.1",
            "-p",
            "background smoke",
        ],
        timeout=20,
    )
    assert created.returncode == 0, created.stderr
    run_id = created.stdout.strip()
    assert re.fullmatch(r"r[0-9]+", run_id), created.stdout

    waited = run_meridian(
        [
            "--json",
            "run",
            "wait",
            run_id,
            "--timeout-secs",
            "30",
        ],
        timeout=35,
    )
    payload = json.loads(waited.stdout)
    assert payload["run_id"] == run_id
    if payload["status"] == "succeeded":
        assert waited.returncode == 0, waited.stderr
    else:
        assert waited.returncode == 1, waited.stderr
