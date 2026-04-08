"""Doctor warning regressions."""

from pathlib import Path

import pytest

from meridian.lib.ops import diag
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
            count=2,
            names=("meridian-base", "meridian-dev-workflow"),
        ),
    )

    result = doctor_sync(DoctorInput(repo_root=repo_root.as_posix()))

    assert result.outdated_dependencies_warning == diag.UpgradeAvailability(
        count=2,
        names=("meridian-base", "meridian-dev-workflow"),
    )
    assert result.updates_check_warning is None
    assert any(
        warning.startswith(
            "2 dependency updates available (meridian-base, meridian-dev-workflow)."
        )
        for warning in result.warnings
    )


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
