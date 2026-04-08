"""Doctor warning regressions."""

import json
import subprocess
from pathlib import Path

import pytest

from meridian.lib.ops import diag
from meridian.lib.ops import mars as mars_ops
from meridian.lib.ops.diag import DoctorInput, doctor_sync


def _create_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def test_doctor_reports_outdated_dependency_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _create_repo_root(tmp_path)
    monkeypatch.setattr(
        diag,
        "check_upgrade_availability",
        lambda *_args, **_kwargs: diag.UpgradeAvailability(
            within_constraint=("meridian-dev-workflow",),
            beyond_constraint=("meridian-base",),
        ),
    )

    result = doctor_sync(DoctorInput(repo_root=repo_root.as_posix()))

    assert result.outdated_dependencies_warning == diag.UpgradeAvailability(
        within_constraint=("meridian-dev-workflow",),
        beyond_constraint=("meridian-base",),
    )
    assert result.updates_check_warning is None
    warning = next(
        warning for warning in result.warnings if "pinned constraint" in warning
    )
    assert (
        "1 dependency update available within your pinned constraint: "
        "meridian-dev-workflow." in warning
    )
    assert "Run `meridian mars upgrade` to apply." in warning
    assert (
        "1 newer version available beyond your pinned constraint: "
        "meridian-base." in warning
    )
    assert "Edit mars.toml to bump the version, then run `meridian mars sync`." in warning


def test_doctor_reports_update_check_failure_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _create_repo_root(tmp_path)
    monkeypatch.setattr(
        diag,
        "check_upgrade_availability",
        lambda *_args, **_kwargs: None,
    )

    result = doctor_sync(DoctorInput(repo_root=repo_root.as_posix()))

    assert result.outdated_dependencies_warning is None
    assert result.updates_check_warning is not None
    assert result.updates_check_warning in result.warnings


def test_doctor_surfaces_beyond_constraint_warning_from_outdated_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _create_repo_root(tmp_path)
    monkeypatch.setattr(mars_ops, "resolve_mars_executable", lambda: "/usr/bin/mars")
    real_run = subprocess.run
    outdated_payload = [
        {
            "source": "meridian-base",
            "locked": "v0.0.11",
            "constraint": "v0.0.11",
            "updateable": "v0.0.11",
            "latest": "v0.0.12",
        }
    ]

    def _fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if len(command) >= 2 and command[1] == "outdated":
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps(outdated_payload),
                stderr="",
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr(mars_ops.subprocess, "run", _fake_run)

    result = doctor_sync(DoctorInput(repo_root=repo_root.as_posix()))

    assert result.outdated_dependencies_warning == diag.UpgradeAvailability(
        within_constraint=(),
        beyond_constraint=("meridian-base",),
    )
    warning = next(
        warning
        for warning in result.warnings
        if "newer version available beyond your pinned constraint" in warning
    )
    assert (
        "1 newer version available beyond your pinned constraint: meridian-base."
        in warning
    )
    assert "Edit mars.toml to bump the version, then run `meridian mars sync`." in warning
