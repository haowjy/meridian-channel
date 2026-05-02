from pathlib import Path

import pytest

from meridian.lib.ops.workspace import (
    MigratedEntry,
    _deduplicate_names,
    _generate_entry_name,
    _has_workspace_section_or_scaffold,
    _migration_block,
    _strip_workspace_sections,
)


@pytest.mark.parametrize(
    ("basename", "expected"),
    [
        ("Sibling Repo", "sibling-repo"),
        ("MIXED_case.repo", "mixed-case-repo"),
        ("---", None),
        ("", None),
        (".", None),
        ("..", None),
        ("/", None),
    ],
)
def test_generate_entry_name_normalizes_directory_basenames(
    basename: str,
    expected: str | None,
) -> None:
    assert _generate_entry_name(basename) == expected


def test_deduplicate_names_uses_case_insensitive_numeric_suffixes() -> None:
    assert _deduplicate_names(["Docs", "docs", "DOCS-2", "docs"]) == [
        "docs",
        "docs-2",
        "docs-2-2",
        "docs-3",
    ]


def test_has_workspace_section_or_scaffold_accepts_commented_scaffold(tmp_path: Path) -> None:
    config_path = tmp_path / "meridian.local.toml"
    config_path.write_text(
        '# comment\n# [workspace.example]\n# path = "../sibling"\n',
        encoding="utf-8",
    )

    assert _has_workspace_section_or_scaffold(config_path) is True


def test_has_workspace_section_or_scaffold_raises_on_invalid_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "meridian.local.toml"
    config_path.write_text("[workspace.example\npath = \"../broken\"\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid TOML"):
        _has_workspace_section_or_scaffold(config_path)


def test_strip_workspace_sections_removes_workspace_tables_and_preserves_other_content() -> None:
    original = (
        '[defaults]\nmodel = "gpt-5.4"\n\n'
        '[workspace.docs]\npath = "../docs"\ncomment = "remove me"\n\n'
        '[workspace.tools]\npath = "../tools"\n\n'
        '[primary]\nmodel = "reviewer"\n'
    )

    assert _strip_workspace_sections(original) == (
        '[defaults]\nmodel = "gpt-5.4"\n\n[primary]\nmodel = "reviewer"'
    )


def test_migration_block_renders_workspace_entries_with_escaped_paths() -> None:
    block = _migration_block(
        (
            MigratedEntry(name="docs", original_path='../docs"quoted"'),
            MigratedEntry(name="notes", original_path="../notes\\nested"),
        )
    )

    assert block == (
        "# Auto-migrated from workspace.local.toml by `meridian workspace migrate`.\n\n"
        "[workspace.docs]\n"
        'path = "../docs\\"quoted\\""\n\n'
        "[workspace.notes]\n"
        'path = "../notes\\\\nested"\n'
    )


def test_migration_block_emits_header_when_no_entries_exist() -> None:
    assert _migration_block(()) == (
        "# Auto-migrated from workspace.local.toml by `meridian workspace migrate`.\n"
    )
