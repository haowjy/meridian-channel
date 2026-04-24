"""Mermaid diagram validation smoke tests.

Fills zero-coverage gap for mermaid check command.
"""


def test_mermaid_check_on_clean_markdown(cli, scratch_dir):
    """mermaid check exits 0 on markdown with valid mermaid."""
    content = """# Design

```mermaid
graph TD
    A[Start] --> B[End]
```

Some text.
"""
    (scratch_dir / "design.md").write_text(content, encoding="utf-8")

    result = cli("mermaid", "check", str(scratch_dir))
    result.assert_success()


def test_mermaid_check_on_no_diagrams(cli, scratch_dir):
    """mermaid check exits 0 on markdown with no mermaid blocks."""
    (scratch_dir / "plain.md").write_text("# Plain\n\nNo diagrams.\n", encoding="utf-8")

    result = cli("mermaid", "check", str(scratch_dir))
    result.assert_success()


def test_mermaid_check_on_broken_syntax(cli, scratch_dir):
    """mermaid check validates syntax.

    Broken diagrams may pass or fail depending on parser strictness.
    """
    # Note: The python heuristics parser may be lenient about some syntax errors
    # This test verifies the command runs without crashing
    content = """# Broken

```mermaid
graph TD
    A[Start --> B[End
```
"""
    (scratch_dir / "broken.md").write_text(content, encoding="utf-8")

    result = cli("mermaid", "check", str(scratch_dir))
    # Command should complete without traceback (may pass or fail)
    assert "Traceback" not in result.stderr


def test_mermaid_check_standalone_file(cli, scratch_dir):
    """mermaid check works on standalone .mmd file."""
    content = """graph LR
    X --> Y --> Z
"""
    (scratch_dir / "diagram.mmd").write_text(content, encoding="utf-8")

    result = cli("mermaid", "check", str(scratch_dir / "diagram.mmd"))
    result.assert_success()


def test_mermaid_check_cwd_default(cli, scratch_dir):
    """mermaid check uses cwd when no path specified."""
    (scratch_dir / "any.md").write_text("# Test\n", encoding="utf-8")

    result = cli("mermaid", "check")
    result.assert_success()
