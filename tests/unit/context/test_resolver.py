"""Unit tests for context path resolution helpers."""

from pathlib import Path

import pytest

from meridian.lib.config.context_config import ContextConfig, ContextSourceType
from meridian.lib.context.resolver import resolve_context_paths


def test_resolve_context_paths_relative_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    config = ContextConfig.model_validate(
        {
            "work": {"path": "state/work", "archive": "state/archive/work"},
            "kb": {"path": "state/kb"},
        }
    )

    resolved = resolve_context_paths(project_root, config, project_uuid="project-id")

    assert resolved.work_root == project_root / "state/work"
    assert resolved.work_archive == project_root / "state/archive/work"
    assert resolved.kb_root == project_root / "state/kb"


def test_resolve_context_paths_expands_home_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "repo"
    home_root = tmp_path / "home"
    project_root.mkdir()
    home_root.mkdir()
    monkeypatch.setenv("HOME", home_root.as_posix())
    monkeypatch.setenv("USERPROFILE", home_root.as_posix())

    config = ContextConfig.model_validate(
        {
            "work": {"path": "~/work-dir", "archive": "~/archive/work"},
            "kb": {"path": "~/kb-dir"},
        }
    )

    resolved = resolve_context_paths(project_root, config, project_uuid="project-id")

    assert resolved.work_root == home_root / "work-dir"
    assert resolved.work_archive == home_root / "archive/work"
    assert resolved.kb_root == home_root / "kb-dir"


def test_resolve_context_paths_absolute_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    absolute_root = tmp_path / "external"

    config = ContextConfig.model_validate(
        {
            "work": {
                "path": (absolute_root / "work").as_posix(),
                "archive": (absolute_root / "archive/work").as_posix(),
            },
            "kb": {"path": (absolute_root / "kb").as_posix()},
        },
    )

    resolved = resolve_context_paths(project_root, config, project_uuid="project-id")

    assert resolved.work_root == absolute_root / "work"
    assert resolved.work_archive == absolute_root / "archive/work"
    assert resolved.kb_root == absolute_root / "kb"


def test_resolve_context_paths_substitutes_project_uuid_from_state_id(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    meridian_dir = project_root / ".meridian"
    project_root.mkdir()
    meridian_dir.mkdir()
    (meridian_dir / "id").write_text("project-uuid-1234", encoding="utf-8")

    config = ContextConfig.model_validate(
        {
            "work": {
                "path": "contexts/{project}/work",
                "archive": "contexts/{project}/archive/work",
            },
            "kb": {"path": "contexts/{project}/kb"},
        },
    )

    resolved = resolve_context_paths(project_root, config)

    assert resolved.work_root == project_root / "contexts/project-uuid-1234/work"
    assert resolved.work_archive == project_root / "contexts/project-uuid-1234/archive/work"
    assert resolved.kb_root == project_root / "contexts/project-uuid-1234/kb"


def test_resolve_context_paths_git_source_with_empty_remote_falls_back_to_project_root(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    config = ContextConfig.model_validate(
        {
            "work": {
                "source": ContextSourceType.GIT.value,
                "remote": "",
                "path": ".meridian/work",
                "archive": ".meridian/archive/work",
            },
            "kb": {
                "source": ContextSourceType.GIT.value,
                "remote": "   ",
                "path": ".meridian/kb",
            },
        }
    )

    resolved = resolve_context_paths(project_root, config, project_uuid="project-id")

    assert resolved.work_root == project_root / ".meridian/work"
    assert resolved.work_archive == project_root / ".meridian/archive/work"
    assert resolved.kb_root == project_root / ".meridian/kb"


def test_resolve_context_paths_git_source_with_remote_uses_clone_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    clone_root = tmp_path / "clones" / "ctx"
    remote = "https://example.com/acme/context.git"

    monkeypatch.setattr(
        "meridian.lib.context.resolver.resolve_clone_path",
        lambda repo_url: clone_root if repo_url == remote else Path("/unexpected"),
    )

    config = ContextConfig.model_validate(
        {
            "work": {
                "source": ContextSourceType.GIT.value,
                "remote": remote,
                "path": ".meridian/work",
                "archive": ".meridian/archive/work",
            },
            "kb": {
                "source": ContextSourceType.GIT.value,
                "remote": remote,
                "path": ".meridian/kb",
            },
        }
    )

    resolved = resolve_context_paths(project_root, config, project_uuid="project-id")

    assert resolved.work_root == clone_root / ".meridian/work"
    assert resolved.work_archive == clone_root / ".meridian/archive/work"
    assert resolved.kb_root == clone_root / ".meridian/kb"
