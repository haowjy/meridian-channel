from __future__ import annotations

import os
from pathlib import Path

from meridian.lib.sync.config import SyncSourceConfig
from meridian.lib.sync.engine import (
    _create_claude_symlink,
    _is_sync_managed_symlink,
    _splice_frontmatter,
    check_cross_source_collisions,
    discover_items,
    sync_items,
)
from meridian.lib.sync.hash import compute_item_hash
from meridian.lib.sync.lock import read_lock_file


def test_discover_items_applies_include_exclude_and_rename_using_source_names(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_source_skill(source_dir, "keep-me", "Keep me.\n")
    _write_source_skill(source_dir, "rename-me", "Rename me.\n")
    _write_source_skill(source_dir, "skip-me", "Skip me.\n")
    _write_source_agent(source_dir, "agent-one", "Agent one.\n")
    _write_source_agent(source_dir, "agent-two", "Agent two.\n")
    _write_source_agent(source_dir, "agent-three", "Agent three.\n")

    items = discover_items(
        SyncSourceConfig(
            name="local",
            path=str(source_dir),
            skills=("keep-me", "rename-me"),
            agents=("agent-one", "agent-two"),
            exclude_skills=("keep-me",),
            exclude_agents=("agent-two",),
            rename={"rename-me": "renamed-skill", "agent-one": "local-agent"},
        ),
        source_dir,
    )

    assert items == [
        ("skill", "rename-me", "renamed-skill"),
        ("agent", "agent-one", "local-agent"),
    ]


def test_check_cross_source_collisions_detects_duplicate_destination_name() -> None:
    try:
        check_cross_source_collisions(
            [
                ("skill", "deploy-checklist", "personal", "owner/personal"),
                ("skill", "deploy-checklist", "team", "owner/team"),
            ]
        )
    except ValueError as exc:
        assert "deploy-checklist" in str(exc)
        assert "personal" in str(exc)
        assert "team" in str(exc)
    else:
        raise AssertionError("Expected a cross-source collision error.")


def test_splice_frontmatter_preserves_local_frontmatter_and_uses_source_body() -> None:
    local_text = "---\nname: local\nmodel: gpt-5\n---\nLocal body.\n"
    source_text = "---\nname: source\nmodel: claude\n---\nSource body.\n"

    assert _splice_frontmatter(local_text, source_text) == (
        "---\nname: local\nmodel: gpt-5\n---\nSource body.\n"
    )


def test_splice_frontmatter_uses_source_text_when_source_has_no_frontmatter() -> None:
    local_text = "---\nname: local\nmodel: gpt-5\n---\nLocal body.\n"
    source_text = "# Source\n\nBody.\n"

    assert _splice_frontmatter(local_text, source_text) == (
        "---\nname: local\nmodel: gpt-5\n---\n# Source\n\nBody.\n"
    )


def test_sync_items_update_preserves_local_frontmatter(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_dir = tmp_path / "source"
    repo_root.mkdir()
    _write_source_skill(source_dir, "review", "Original body.\n")

    first = _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)))
    assert _action_by_key(first, "skills/review").action == "installed"

    skill_path = repo_root / ".agents" / "skills" / "review" / "SKILL.md"
    skill_path.write_text(
        "---\nname: review\nmodel: local-custom\nsandbox: workspace-write\n---\nOriginal body.\n",
        encoding="utf-8",
    )
    _write_source_skill(
        source_dir,
        "review",
        "Updated upstream body.\n",
        frontmatter_lines=("name: review", "model: upstream-model"),
    )

    result = _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)))

    assert _action_by_key(result, "skills/review").action == "updated"
    assert skill_path.read_text(encoding="utf-8") == (
        "---\nname: review\nmodel: local-custom\nsandbox: workspace-write\n---\n"
        "Updated upstream body.\n"
    )


def test_sync_items_conflict_when_local_and_source_bodies_diverge(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_dir = tmp_path / "source"
    repo_root.mkdir()
    _write_source_skill(source_dir, "review", "Original body.\n")

    _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)))
    skill_path = repo_root / ".agents" / "skills" / "review" / "SKILL.md"
    skill_path.write_text(
        "---\nname: review\nmodel: local\n---\nLocal edited body.\n",
        encoding="utf-8",
    )
    _write_source_skill(source_dir, "review", "Upstream edited body.\n")

    previous_hash = read_lock_file(repo_root / ".meridian" / "sync.lock").items[
        "skills/review"
    ].tree_hash
    result = _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)))

    assert _action_by_key(result, "skills/review").action == "conflict"
    assert skill_path.read_text(encoding="utf-8") == (
        "---\nname: review\nmodel: local\n---\nLocal edited body.\n"
    )
    assert read_lock_file(repo_root / ".meridian" / "sync.lock").items[
        "skills/review"
    ].tree_hash == previous_hash


def test_sync_items_force_overwrites_diverged_local_content(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_dir = tmp_path / "source"
    repo_root.mkdir()
    _write_source_skill(source_dir, "review", "Original body.\n")

    _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)))
    skill_path = repo_root / ".agents" / "skills" / "review" / "SKILL.md"
    skill_path.write_text(
        "---\nname: review\nmodel: local-custom\n---\nLocal edited body.\n",
        encoding="utf-8",
    )
    _write_source_skill(
        source_dir,
        "review",
        "Upstream edited body.\n",
        frontmatter_lines=("name: review", "model: upstream-model"),
    )

    result = _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)), force=True)

    assert _action_by_key(result, "skills/review").action == "reinstalled"
    assert skill_path.read_text(encoding="utf-8") == (
        "---\nname: review\nmodel: upstream-model\n---\nUpstream edited body.\n"
    )


def test_sync_items_blocks_unmanaged_claude_conflicts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_dir = tmp_path / "source"
    repo_root.mkdir()
    _write_source_skill(source_dir, "review", "Original body.\n")
    (repo_root / ".claude" / "skills" / "review").mkdir(parents=True)

    result = _sync(repo_root, SyncSourceConfig(name="local", path=str(source_dir)))

    assert _action_by_key(result, "skills/review").action == "conflict"
    assert not (repo_root / ".agents" / "skills" / "review").exists()
    assert read_lock_file(repo_root / ".meridian" / "sync.lock").items == {}


def _sync(
    repo_root: Path,
    source: SyncSourceConfig,
    *,
    force: bool = False,
    dry_run: bool = False,
    prune: bool = False,
) -> object:
    return sync_items(
        repo_root=repo_root,
        sources=(source,),
        sync_cache_dir=repo_root / ".meridian" / "cache" / "sync",
        sync_lock_path=repo_root / ".meridian" / "sync.lock",
        force=force,
        dry_run=dry_run,
        prune=prune,
    )


def _action_by_key(result: object, item_key: str) -> object:
    actions = {action.item_key: action for action in result.actions}
    return actions[item_key]


def _write_source_skill(
    source_dir: Path,
    name: str,
    body: str,
    *,
    frontmatter_lines: tuple[str, ...] = ("name: {name}", "model: source-model"),
    extra_files: dict[str, str] | None = None,
) -> None:
    skill_dir = source_dir / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    rendered_lines = tuple(line.format(name=name) for line in frontmatter_lines)
    (skill_dir / "SKILL.md").write_text(
        "---\n" + "\n".join(rendered_lines) + "\n---\n" + body,
        encoding="utf-8",
    )
    for relative_path, content in (extra_files or {}).items():
        target = skill_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _write_source_agent(
    source_dir: Path,
    name: str,
    body: str,
) -> None:
    agents_dir = source_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\nmodel: source-model\n---\n{body}",
        encoding="utf-8",
    )
