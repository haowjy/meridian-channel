"""Tests for Mars operation helpers."""

import json
import subprocess
from pathlib import Path

import pytest

from meridian.lib.ops import mars


def test_check_upgrade_availability_filters_head_and_noop_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mars, "resolve_mars_executable", lambda: "/usr/bin/mars")
    payload = [
        {
            "source": "meridian-base",
            "locked": "v0.1.0",
            "constraint": "^0.1",
            "updateable": "v0.1.2",
            "latest": "v0.1.2",
        },
        {
            "source": "anthropic-skills",
            "locked": "aabbccddeeff",
            "constraint": "HEAD",
            "updateable": "112233445566",
            "latest": "112233445566",
        },
        {
            "source": "meridian-dev-workflow",
            "locked": "v0.4.1",
            "constraint": "^0.4",
            "updateable": "v0.4.1",
            "latest": "v0.5.0",
        },
    ]

    def _fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["/usr/bin/mars", "outdated", "--json"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(mars.subprocess, "run", _fake_run)

    availability = mars.check_upgrade_availability()

    assert availability == mars.UpgradeAvailability(count=1, names=("meridian-base",))


def test_check_upgrade_availability_passes_root_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(mars, "resolve_mars_executable", lambda: "/usr/bin/mars")
    observed: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.append(cmd)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="[]",
            stderr="",
        )

    monkeypatch.setattr(mars.subprocess, "run", _fake_run)

    availability = mars.check_upgrade_availability(tmp_path)

    assert availability == mars.UpgradeAvailability(count=0, names=())
    assert observed and observed[0][-2:] == ["--root", tmp_path.as_posix()]


@pytest.mark.parametrize(
    "completed",
    [
        subprocess.CompletedProcess(
            args=["/usr/bin/mars", "outdated", "--json"],
            returncode=2,
            stdout="",
            stderr="boom",
        ),
        subprocess.CompletedProcess(
            args=["/usr/bin/mars", "outdated", "--json"],
            returncode=0,
            stdout="{not-json}",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=["/usr/bin/mars", "outdated", "--json"],
            returncode=0,
            stdout='{"not":"a-list"}',
            stderr="",
        ),
    ],
)
def test_check_upgrade_availability_returns_none_on_failures(
    monkeypatch: pytest.MonkeyPatch,
    completed: subprocess.CompletedProcess[str],
) -> None:
    monkeypatch.setattr(mars, "resolve_mars_executable", lambda: "/usr/bin/mars")
    monkeypatch.setattr(mars.subprocess, "run", lambda *_args, **_kwargs: completed)

    assert mars.check_upgrade_availability() is None


def test_check_upgrade_availability_returns_none_without_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mars, "resolve_mars_executable", lambda: None)

    assert mars.check_upgrade_availability() is None


def test_format_upgrade_hint_lines() -> None:
    lines = mars.format_upgrade_hint_lines(
        mars.UpgradeAvailability(
            count=2,
            names=("meridian-base", "meridian-dev-workflow"),
        )
    )
    assert lines == (
        "hint: 2 updates available (meridian-base, meridian-dev-workflow).",
        "      Run `meridian mars outdated` to see details, or "
        "`meridian mars upgrade` to apply.",
    )
