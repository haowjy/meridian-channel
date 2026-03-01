"""Harness materialization tests."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.config.agent import AgentProfile
from meridian.lib.config.skill import split_markdown_frontmatter
from meridian.lib.harness.materialize import (
    _reconstruct_builtin_agent,
    _rewrite_agent_skills,
    cleanup_all_materialized,
    cleanup_materialized,
    materialize_for_harness,
)


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_skill_dir(root: Path, skill_name: str, *, with_nested: bool = False) -> Path:
    skill_dir = root / skill_name
    _write(skill_dir / "SKILL.md", f"# {skill_name}\n")
    if with_nested:
        _write(skill_dir / "scripts" / "run.sh", "echo run\n")
    return skill_dir


def _make_profile(
    *,
    name: str = "primary",
    skills: tuple[str, ...] = (),
    raw_content: str = "",
    model: str | None = "gpt-5.3-codex",
    sandbox: str | None = "workspace-write",
    body: str = "",
) -> AgentProfile:
    return AgentProfile(
        name=name,
        description="",
        model=model,
        variant=None,
        skills=skills,
        allowed_tools=(),
        mcp_tools=(),
        sandbox=sandbox,
        variant_models=(),
        body=body,
        path=Path("/tmp") / f"{name}.md",
        raw_content=raw_content,
    )


def test_rewrite_agent_skills_preserves_other_content() -> None:
    raw = (
        "---\n"
        "name: reviewer\n"
        "unknown-key: keep-me\n"
        "skills: [alpha, beta, keep]\n"
        "sandbox: workspace-write\n"
        "---\n"
        "Body line\n"
        "skills: [alpha]\n"
    )

    rewritten = _rewrite_agent_skills(
        raw,
        {
            "alpha": "_meridian-c1-alpha",
            "beta": "_meridian-c1-beta",
        },
    )

    # Verify non-skills frontmatter and body are preserved via parsing
    fm, body = split_markdown_frontmatter(rewritten)
    assert fm["name"] == "reviewer"
    assert fm["unknown-key"] == "keep-me"
    assert fm["sandbox"] == "workspace-write"
    # Skills should be remapped; unmapped entries are passed through
    assert fm["skills"] == ["_meridian-c1-alpha", "_meridian-c1-beta", "keep"]
    # Body outside frontmatter must not be touched
    assert "Body line" in body
    assert "skills: [alpha]" in body


def test_rewrite_agent_skills_without_skills_key_leaves_other_data_intact() -> None:
    # python-frontmatter round-trips YAML so exact byte equality is not guaranteed,
    # but all keys and values must survive unchanged when there is no skills entry.
    raw = "---\nname: reviewer\nmodel: gpt-5\n---\nBody\n"
    rewritten = _rewrite_agent_skills(raw, {"x": "y"})
    fm, body = split_markdown_frontmatter(rewritten)
    assert fm["name"] == "reviewer"
    assert fm["model"] == "gpt-5"
    assert "skills" not in fm
    assert "Body" in body


def test_rewrite_agent_skills_preserves_inline_quoted_items() -> None:
    # YAML parses quoted "true"/"null"/"42" as strings; after round-trip the values
    # must still be strings (not booleans/None/integers).
    raw = "---\nname: reviewer\nskills: [\"true\", \"null\", \"42\"]\n---\nBody\n"

    rewritten = _rewrite_agent_skills(raw, {})

    fm, _ = split_markdown_frontmatter(rewritten)
    assert fm["skills"] == ["true", "null", "42"]


def test_rewrite_agent_skills_maps_inline_quoted_item() -> None:
    raw = "---\nname: reviewer\nskills: [\"alpha\"]\n---\nBody\n"

    rewritten = _rewrite_agent_skills(raw, {"alpha": "_meridian-c1-alpha"})

    fm, _ = split_markdown_frontmatter(rewritten)
    assert fm["skills"] == ["_meridian-c1-alpha"]


def test_rewrite_agent_skills_block_style_maps_item() -> None:
    # Comments in YAML are not preserved by python-frontmatter; verify the item is
    # correctly mapped regardless of the style used in the output.
    raw = "---\nname: reviewer\nskills:\n  - alpha\n---\nBody\n"

    rewritten = _rewrite_agent_skills(raw, {"alpha": "_meridian-c1-alpha"})

    fm, _ = split_markdown_frontmatter(rewritten)
    assert fm["skills"] == ["_meridian-c1-alpha"]


def test_reconstruct_builtin_agent_generates_minimal_markdown() -> None:
    profile = _make_profile(
        name="agent",
        skills=("reviewing",),
        raw_content="",
        model="gpt-5.3-codex",
        sandbox="workspace-write",
        body="Builtin body\n",
    )

    rendered = _reconstruct_builtin_agent(
        profile,
        ["_meridian-c1-reviewing", "native-skill"],
        materialized_name="_meridian-c1-agent",
    )
    frontmatter, body = split_markdown_frontmatter(rendered)

    assert frontmatter["name"] == "_meridian-c1-agent"
    assert frontmatter["model"] == "gpt-5.3-codex"
    assert frontmatter["skills"] == ["_meridian-c1-reviewing", "native-skill"]
    assert frontmatter["sandbox"] == "workspace-write"
    assert body == "Builtin body"


def test_materialize_for_harness_all_native_makes_no_writes(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / ".agents" / "agents" / "primary.md", "# primary\n")
    alpha_dir = _make_skill_dir(repo_root / ".agents" / "skills", "alpha")
    beta_dir = _make_skill_dir(repo_root / ".agents" / "skills", "beta")

    profile = _make_profile(
        skills=("alpha", "beta"),
        raw_content="---\nname: primary\nskills: [alpha, beta]\n---\nBody\n",
    )

    result = materialize_for_harness(
        agent_profile=profile,
        skill_sources={"alpha": alpha_dir, "beta": beta_dir},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
    )

    assert result.agent_name == "primary"
    assert not result.materialized_agent
    assert result.materialized_skills == ()
    assert result.native
    assert not (repo_root / ".agents" / "agents" / "_meridian-c1-primary.md").exists()
    assert not any((repo_root / ".agents" / "skills").glob("_meridian-c1-*"))


def test_materialize_for_harness_mixed_rewrites_agent_and_copies_missing(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / ".agents" / "agents" / "primary.md", "# primary\n")
    alpha_native = _make_skill_dir(repo_root / ".agents" / "skills", "alpha")

    sources_root = repo_root / "source-skills"
    beta_source = _make_skill_dir(sources_root, "beta")

    profile = _make_profile(
        skills=("alpha", "beta"),
        raw_content=(
            "---\n"
            "name: primary\n"
            "description: keep\n"
            "skills: [alpha, beta]\n"
            "---\n"
            "Agent body\n"
        ),
    )

    result = materialize_for_harness(
        agent_profile=profile,
        skill_sources={"alpha": alpha_native, "beta": beta_source},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
    )

    assert result.agent_name == "_meridian-c1-primary"
    assert result.materialized_agent
    assert result.materialized_skills == ("_meridian-c1-beta",)
    assert not result.native

    materialized_skill = repo_root / ".agents" / "skills" / "_meridian-c1-beta"
    assert (materialized_skill / "SKILL.md").is_file()

    materialized_agent_file = repo_root / ".agents" / "agents" / "_meridian-c1-primary.md"
    rewritten = materialized_agent_file.read_text(encoding="utf-8")
    fm, _ = split_markdown_frontmatter(rewritten)
    assert fm["name"] == "_meridian-c1-primary"
    assert fm["description"] == "keep"
    assert fm["skills"] == ["alpha", "_meridian-c1-beta"]


def test_materialize_for_harness_rewrites_skill_name_in_frontmatter(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    source_skill_dir = repo_root / "source-skills" / "meridian-run"
    _write(
        source_skill_dir / "SKILL.md",
        "---\nname: meridian-run\ndescription: test skill\n---\nBody\n",
    )

    result = materialize_for_harness(
        agent_profile=None,
        skill_sources={"meridian-run": source_skill_dir},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
    )

    assert result.materialized_skills == ("_meridian-c1-meridian-run",)
    materialized_skill = repo_root / ".agents" / "skills" / "_meridian-c1-meridian-run" / "SKILL.md"
    frontmatter, body = split_markdown_frontmatter(materialized_skill.read_text(encoding="utf-8"))
    assert frontmatter["name"] == "_meridian-c1-meridian-run"
    assert frontmatter["description"] == "test skill"
    assert body == "Body"


def test_materialize_for_harness_all_missing_materializes_all(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    sources_root = repo_root / "source-skills"
    alpha_source = _make_skill_dir(sources_root, "alpha")
    beta_source = _make_skill_dir(sources_root, "beta")

    profile = _make_profile(
        skills=("alpha", "beta"),
        raw_content="---\nname: primary\nskills: [alpha, beta]\n---\nBody\n",
    )

    result = materialize_for_harness(
        agent_profile=profile,
        skill_sources={"alpha": alpha_source, "beta": beta_source},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
    )

    assert result.agent_name == "_meridian-c1-primary"
    assert result.materialized_agent
    assert result.materialized_skills == ("_meridian-c1-alpha", "_meridian-c1-beta")
    assert not result.native

    rewritten = (
        repo_root / ".agents" / "agents" / "_meridian-c1-primary.md"
    ).read_text(encoding="utf-8")
    fm, _ = split_markdown_frontmatter(rewritten)
    assert fm["skills"] == ["_meridian-c1-alpha", "_meridian-c1-beta"]
    assert (repo_root / ".agents" / "skills" / "_meridian-c1-alpha" / "SKILL.md").is_file()
    assert (repo_root / ".agents" / "skills" / "_meridian-c1-beta" / "SKILL.md").is_file()


def test_materialize_for_harness_copies_full_skill_tree(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    sources_root = repo_root / "source-skills"
    tree_source = _make_skill_dir(sources_root, "tree", with_nested=True)

    result = materialize_for_harness(
        agent_profile=None,
        skill_sources={"tree": tree_source},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
    )

    assert result.materialized_skills == ("_meridian-c1-tree",)
    copied = repo_root / ".agents" / "skills" / "_meridian-c1-tree"
    assert (copied / "SKILL.md").is_file()
    assert (copied / "scripts" / "run.sh").is_file()


def test_materialize_for_harness_dry_run_writes_nothing(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source = _make_skill_dir(repo_root / "sources", "alpha")
    profile = _make_profile(
        skills=("alpha",),
        raw_content="---\nname: primary\nskills: [alpha]\n---\n",
    )

    result = materialize_for_harness(
        agent_profile=profile,
        skill_sources={"alpha": source},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
        dry_run=True,
    )

    assert result.agent_name == "_meridian-c1-primary"
    assert result.materialized_agent
    assert result.materialized_skills == ("_meridian-c1-alpha",)
    assert not (repo_root / ".agents" / "agents").exists()
    assert not (repo_root / ".agents" / "skills" / "_meridian-c1-alpha").exists()


def test_materialize_for_harness_builtin_agent_reconstructed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source = _make_skill_dir(repo_root / "sources", "reviewing")

    profile = _make_profile(
        name="agent",
        skills=("reviewing",),
        raw_content="",
        model="gpt-5.3-codex",
        sandbox="workspace-write",
        body="Builtin body\n",
    )

    result = materialize_for_harness(
        agent_profile=profile,
        skill_sources={"reviewing": source},
        harness_id="codex",
        repo_root=repo_root,
        chat_id="c1",
    )

    assert result.agent_name == "_meridian-c1-agent"
    rendered = (
        repo_root / ".agents" / "agents" / "_meridian-c1-agent.md"
    ).read_text(encoding="utf-8")
    frontmatter, body = split_markdown_frontmatter(rendered)
    assert frontmatter["name"] == "_meridian-c1-agent"
    assert frontmatter["model"] == "gpt-5.3-codex"
    assert frontmatter["skills"] == ["_meridian-c1-reviewing"]
    assert frontmatter["sandbox"] == "workspace-write"
    assert body == "Builtin body"


def test_cleanup_materialized_removes_only_matching_chat_scope(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / ".agents" / "agents" / "_meridian-c1-primary.md", "x")
    _write(repo_root / ".agents" / "agents" / "_meridian-c2-primary.md", "x")
    _write(repo_root / ".agents" / "agents" / "primary.md", "x")

    _write(repo_root / ".agents" / "skills" / "_meridian-c1-alpha" / "SKILL.md", "x")
    _write(repo_root / ".agents" / "skills" / "_meridian-c2-alpha" / "SKILL.md", "x")
    _write(repo_root / ".agents" / "skills" / "alpha" / "SKILL.md", "x")

    removed = cleanup_materialized("codex", repo_root, "c1")

    assert removed == 2
    assert not (repo_root / ".agents" / "agents" / "_meridian-c1-primary.md").exists()
    assert (repo_root / ".agents" / "agents" / "_meridian-c2-primary.md").is_file()
    assert (repo_root / ".agents" / "agents" / "primary.md").is_file()

    assert not (repo_root / ".agents" / "skills" / "_meridian-c1-alpha").exists()
    assert (repo_root / ".agents" / "skills" / "_meridian-c2-alpha").is_dir()
    assert (repo_root / ".agents" / "skills" / "alpha").is_dir()


def test_cleanup_materialized_escapes_wildcard_chat_id(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / ".agents" / "agents" / "_meridian-c1-foo.md", "x")
    _write(repo_root / ".agents" / "agents" / "_meridian-c2-foo.md", "x")
    _write(repo_root / ".agents" / "skills" / "_meridian-c1-foo" / "SKILL.md", "x")
    _write(repo_root / ".agents" / "skills" / "_meridian-c2-foo" / "SKILL.md", "x")

    removed = cleanup_materialized("codex", repo_root, "c*")

    assert removed == 0
    assert (repo_root / ".agents" / "agents" / "_meridian-c1-foo.md").is_file()
    assert (repo_root / ".agents" / "agents" / "_meridian-c2-foo.md").is_file()
    assert (repo_root / ".agents" / "skills" / "_meridian-c1-foo").is_dir()
    assert (repo_root / ".agents" / "skills" / "_meridian-c2-foo").is_dir()


def test_cleanup_all_materialized_removes_all_prefixed_entries(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / ".agents" / "agents" / "_meridian-c1-primary.md", "x")
    _write(repo_root / ".agents" / "agents" / "_meridian-c2-primary.md", "x")
    _write(repo_root / ".agents" / "agents" / "primary.md", "x")

    _write(repo_root / ".agents" / "skills" / "_meridian-c1-alpha" / "SKILL.md", "x")
    _write(repo_root / ".agents" / "skills" / "_meridian-c2-beta" / "SKILL.md", "x")
    _write(repo_root / ".agents" / "skills" / "alpha" / "SKILL.md", "x")

    removed = cleanup_all_materialized("codex", repo_root)

    assert removed == 4
    assert not (repo_root / ".agents" / "agents" / "_meridian-c1-primary.md").exists()
    assert not (repo_root / ".agents" / "agents" / "_meridian-c2-primary.md").exists()
    assert (repo_root / ".agents" / "agents" / "primary.md").is_file()

    assert not (repo_root / ".agents" / "skills" / "_meridian-c1-alpha").exists()
    assert not (repo_root / ".agents" / "skills" / "_meridian-c2-beta").exists()
    assert (repo_root / ".agents" / "skills" / "alpha").is_dir()


def test_cleanup_never_removes_non_prefixed_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(repo_root / ".agents" / "agents" / "primary.md", "x")
    _write(repo_root / ".agents" / "skills" / "reviewing" / "SKILL.md", "x")

    removed = cleanup_all_materialized("codex", repo_root)

    assert removed == 0
    assert (repo_root / ".agents" / "agents" / "primary.md").is_file()
    assert (repo_root / ".agents" / "skills" / "reviewing" / "SKILL.md").is_file()
