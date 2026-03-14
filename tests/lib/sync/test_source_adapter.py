from pathlib import Path

import pytest

from meridian.lib.sync.install_config import ManagedSourceConfig
from meridian.lib.sync.source_adapter import GitSourceAdapter, PathSourceAdapter, default_source_adapters


def test_default_source_adapters_expose_git_and_path() -> None:
    adapters = default_source_adapters()

    assert set(adapters) == {"git", "path"}


def test_path_source_adapter_resolves_repo_relative_tree(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    tree = repo_root / "tools" / "agents"
    tree.mkdir(parents=True)

    resolved = PathSourceAdapter().resolve(
        ManagedSourceConfig(name="local", kind="path", path="./tools/agents"),
        cache_dir=repo_root / ".meridian" / "cache" / "agents",
        repo_root=repo_root,
    )

    assert resolved.kind == "path"
    assert resolved.locator == "./tools/agents"
    assert resolved.tree_path == tree.resolve()
    assert resolved.resolved_identity == {"path": "./tools/agents"}


def test_path_source_adapter_discovers_items_from_layout(tmp_path: Path) -> None:
    tree = tmp_path / "source"
    (tree / "agents").mkdir(parents=True)
    (tree / "skills" / "demo").mkdir(parents=True)
    (tree / "agents" / "helper.md").write_text("---\nname: helper\n---\n", encoding="utf-8")
    (tree / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")

    items = PathSourceAdapter().describe(tree)

    assert [item.item_id for item in items] == ["agent:helper", "skill:demo"]


def test_git_source_adapter_falls_back_to_github_archive_without_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / ".meridian" / "cache" / "agents"
    installed_tree = cache_dir / "github-source"

    monkeypatch.setattr("meridian.lib.sync.source_adapter._git_cli_available", lambda: False)
    def fake_resolve_commit(owner: str, repo: str, ref: str | None) -> str:
        assert (owner, repo, ref) == ("haowjy", "orchestrate", "main")
        return "abc123"

    monkeypatch.setattr(
        "meridian.lib.sync.source_adapter._resolve_github_commit",
        fake_resolve_commit,
    )

    def fake_populate(owner: str, repo: str, commit: str, cache_path: Path) -> None:
        assert (owner, repo, commit) == ("haowjy", "orchestrate", "abc123")
        (cache_path / "agents").mkdir(parents=True, exist_ok=True)
        (cache_path / "agents" / "helper.md").write_text("---\nname: helper\n---\n", encoding="utf-8")

    monkeypatch.setattr(
        "meridian.lib.sync.source_adapter._populate_github_archive_cache",
        fake_populate,
    )

    resolved = GitSourceAdapter().resolve(
        ManagedSourceConfig(
            name="github-source",
            kind="git",
            url="https://github.com/haowjy/orchestrate.git",
            ref="main",
        ),
        cache_dir=cache_dir,
        repo_root=tmp_path,
    )

    assert resolved.kind == "git"
    assert resolved.tree_path == installed_tree
    assert resolved.resolved_identity == {"commit": "abc123"}
    assert (installed_tree / "agents" / "helper.md").is_file()


def test_git_source_adapter_requires_git_for_non_github_remote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("meridian.lib.sync.source_adapter._git_cli_available", lambda: False)

    try:
        GitSourceAdapter().resolve(
            ManagedSourceConfig(
                name="remote",
                kind="git",
                url="https://example.com/team/repo.git",
                ref="main",
            ),
            cache_dir=tmp_path / ".meridian" / "cache" / "agents",
            repo_root=tmp_path,
        )
    except RuntimeError as exc:
        assert "public GitHub repo" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected non-GitHub remote without git to fail.")
