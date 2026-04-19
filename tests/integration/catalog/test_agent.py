from pathlib import Path

from meridian.lib.catalog.agent import parse_agent_profile


def test_parse_agent_profile_disallowed_tools(tmp_path: Path) -> None:
    profile_path = tmp_path / "coder.md"
    profile_path.write_text(
        "---\n"
        "name: Coder\n"
        "tools:\n"
        "  - Read\n"
        "disallowed-tools:\n"
        "  - Bash\n"
        "  - WebSearch\n"
        "mcp-tools:\n"
        "  - mcpA\n"
        "---\n"
        "\n"
        "Profile body.\n",
        encoding="utf-8",
    )

    profile = parse_agent_profile(profile_path)

    assert profile.tools == ("Read",)
    assert profile.disallowed_tools == ("Bash", "WebSearch")
