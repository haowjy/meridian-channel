"""Agent-mode subcommand help supplements."""

from meridian.cli.agent_help import agent_help_epilogue


def test_agent_mode_spawn_help_includes_agent_notes(cli):
    result = cli("spawn", "--help", env_override={"MERIDIAN_DEPTH": "1"})
    result.assert_success()

    assert "Agent Notes:" in result.stdout
    assert "Lifecycle: queued" in result.stdout
    assert "Which subcommand when:" in result.stdout
    assert "session log" in result.stdout


def test_agent_mode_session_help_uses_renderer_safe_search_placeholders(cli):
    result = cli("session", "--help", env_override={"MERIDIAN_DEPTH": "1"})
    result.assert_success()

    assert "search QUERY REF" in result.stdout
    assert "meridian session search <query> <ref>" not in result.stdout


def test_agent_mode_doctor_help_includes_agent_notes(cli):
    result = cli("doctor", "--help", env_override={"MERIDIAN_DEPTH": "1"})
    result.assert_success()

    assert "Agent Notes:" in result.stdout
    assert "read paths" in result.stdout
    assert "show, list, wait" in result.stdout
    assert "meridian session log SPAWN_ID" in result.stdout


def test_human_mode_spawn_help_omits_agent_notes(cli):
    result = cli("--human", "spawn", "--help", env_override={"MERIDIAN_DEPTH": "1"})
    result.assert_success()

    assert "Agent Notes:" not in result.stdout


def test_agent_help_supplements_restore_between_invocations(cli):
    agent_result = cli("--agent", "config", "--help", env_override={"MERIDIAN_DEPTH": ""})
    agent_result.assert_success()
    assert "Agent Notes:" in agent_result.stdout
    assert "Resolution is per field" in agent_result.stdout

    human_result = cli("--human", "config", "--help", env_override={"MERIDIAN_DEPTH": "1"})
    human_result.assert_success()
    assert "Agent Notes:" not in human_result.stdout


def test_agent_help_epilogue_composes_once_from_base_text() -> None:
    epilogue = agent_help_epilogue("spawn", "Examples:\n")

    assert epilogue is not None
    assert epilogue.count("Agent Notes:") == 1
    assert epilogue.startswith("Examples:\n")
