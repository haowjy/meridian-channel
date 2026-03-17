from pathlib import Path

from meridian.lib.ops.config import ConfigShowInput, config_show_sync


def test_config_show_warns_for_unavailable_configured_default_agent(tmp_path: Path) -> None:
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

    result = config_show_sync(ConfigShowInput(repo_root=repo_root.as_posix()))

    assert result.warning is not None
    assert "defaults.primary_agent" in result.warning
    assert "dev-orchestration" in result.warning
    assert "__meridian-orchestrator" in result.warning
