from pathlib import Path

from meridian.lib.ops.diag import DoctorInput, doctor_sync


def test_doctor_warns_for_unavailable_configured_default_agent(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_root = repo_root / ".meridian"
    state_root.mkdir()
    (state_root / "config.toml").write_text(
        "\n".join(
            [
                "[defaults]",
                'primary_agent = "dev-orchestration"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = doctor_sync(DoctorInput(repo_root=repo_root.as_posix()))

    assert any("defaults.primary_agent" in warning for warning in result.warnings)
    assert any("dev-orchestration" in warning for warning in result.warnings)
    assert any("__meridian-orchestrator" in warning for warning in result.warnings)
