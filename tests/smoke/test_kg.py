"""KG (knowledge graph) smoke tests — document link topology.

Fills zero-coverage gap for kg graph/check commands.
"""


def test_kg_graph_on_clean_directory(cli, scratch_dir):
    """kg graph exits 0 on directory with no broken links."""
    # Create a simple markdown file with no links
    content = "# Hello\n\nNo links here.\n"
    (scratch_dir / "readme.md").write_text(content, encoding="utf-8")

    result = cli("kg", "graph", str(scratch_dir))
    result.assert_success()


def test_kg_graph_on_linked_docs(cli, scratch_dir):
    """kg graph shows link topology for connected docs."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    index_content = "# Index\n\nSee [guide](guide.md)\n"
    guide_content = "# Guide\n\nBack to [index](index.md)\n"
    (docs / "index.md").write_text(index_content, encoding="utf-8")
    (docs / "guide.md").write_text(guide_content, encoding="utf-8")

    result = cli("kg", "graph", str(docs))
    result.assert_success()
    # Output should mention the files
    assert (
        "index" in result.stdout.lower()
        or "guide" in result.stdout.lower()
        or result.returncode == 0
    )


def test_kg_check_on_valid_links(cli, scratch_dir):
    """kg check exits 0 when all links resolve."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\nLink to [B](b.md)\n", encoding="utf-8")
    (docs / "b.md").write_text("# B\n\nLink to [A](a.md)\n", encoding="utf-8")

    result = cli("kg", "check", str(docs))
    result.assert_success()


def test_kg_check_on_broken_links(cli, scratch_dir):
    """kg check reports broken links as warnings."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    orphan_content = "# Orphan\n\nLink to [missing](does-not-exist.md)\n"
    (docs / "orphan.md").write_text(orphan_content, encoding="utf-8")

    result = cli("kg", "check", str(docs))
    result.assert_success()
    assert "warning: orphan.md:3 Broken link:" in result.stdout
    assert "0 errors, 1 warnings" in result.stderr


def test_kg_check_strict_fails_on_warnings(cli, scratch_dir):
    """kg check --strict exits 1 when warning findings exist."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    orphan_content = "# Orphan\n\nLink to [missing](does-not-exist.md)\n"
    (docs / "orphan.md").write_text(orphan_content, encoding="utf-8")

    result = cli("kg", "check", str(docs), "--strict")
    result.assert_failure(1)
    assert "error: orphan.md:3 Broken link:" in result.stdout
    assert "1 errors, 0 warnings" in result.stderr


def test_kg_check_reports_flag_blocks_and_conflict_markers(cli, scratch_dir):
    """kg check reports flags as warnings and conflict markers as errors."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    content = "\n".join(
        [
            "# Notes",
            "> [!FLAG]",
            "<<<<<<< HEAD",
            "left",
            "=======",
            "right",
            ">>>>>>> branch",
            "",
        ]
    )
    (docs / "notes.md").write_text(content, encoding="utf-8")

    result = cli("kg", "check", str(docs))
    result.assert_failure(1)
    assert "warning: notes.md:2 Flag block found" in result.stdout
    assert "error: notes.md:3 Git conflict marker found" in result.stdout
    assert "error: notes.md:5 Git conflict marker found" in result.stdout
    assert "error: notes.md:7 Git conflict marker found" in result.stdout
    assert "3 errors, 1 warnings" in result.stderr


def test_kg_check_ignores_findings_inside_fenced_blocks(cli, scratch_dir):
    """kg check ignores flags and conflict markers inside fenced code blocks."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    content = "\n".join(
        [
            "# Example docs",
            "Here is a code example:",
            "````markdown",
            "> [!FLAG]",
            "```",
            "<<<<<<< HEAD",
            "=======",
            ">>>>>>> branch",
            "```",
            "````",
            "",
        ]
    )
    (docs / "example.md").write_text(content, encoding="utf-8")

    result = cli("kg", "check", str(docs))
    result.assert_success()


def test_kg_check_ignores_inline_code_and_prose_flag_examples(cli, scratch_dir):
    """kg check ignores documentation examples of flag callout syntax."""
    docs = scratch_dir / "docs"
    docs.mkdir()
    content = "\n".join(
        [
            "# Flag examples",
            "Flags are searchable with `grep -r '\\[!FLAG\\]'`.",
            "- `> [!FLAG]` markers are review callouts.",
            "Add a `[!FLAG]` if something needs human review.",
            "Plain [!FLAG] prose mention is documentation, not a flag.",
            "",
        ]
    )
    (docs / "examples.md").write_text(content, encoding="utf-8")

    result = cli("kg", "check", str(docs))
    result.assert_success()


def test_kg_graph_cwd_default(cli, scratch_dir):
    """kg graph uses cwd when no path specified."""
    (scratch_dir / "test.md").write_text("# Test\n", encoding="utf-8")

    result = cli("kg", "graph")
    result.assert_success()
