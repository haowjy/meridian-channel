from pathlib import Path

from meridian.lib.launch.workspace import _format_workspace_source_path


def test_format_workspace_source_path_defaults_to_legacy_filename_when_empty() -> None:
    assert _format_workspace_source_path(project_root=Path("/repo"), source_paths=()) == (
        "workspace.local.toml"
    )


def test_format_workspace_source_path_uses_relative_and_absolute() -> None:
    project_root = Path("/repo")

    assert _format_workspace_source_path(
        project_root=project_root,
        source_paths=(project_root / "meridian.toml", Path("/tmp/meridian.local.toml")),
    ) == "meridian.toml, /tmp/meridian.local.toml"
