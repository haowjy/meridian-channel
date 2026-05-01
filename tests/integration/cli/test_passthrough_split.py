import importlib

cli_main = importlib.import_module("meridian.cli.main")


def _split_spawn_args(argv: list[str]) -> tuple[list[str], tuple[str, ...]]:
    cleaned, _options = cli_main._extract_global_options(argv)
    return cli_main._split_passthrough_args(cleaned)


def test_split_passthrough_with_prompt_literal() -> None:
    cleaned, passthrough = _split_spawn_args([
        "spawn",
        "-p",
        "hello",
        "--",
        "--add-dir",
        "/foo",
    ])

    assert cleaned == ["spawn", "-p", "hello"]
    assert passthrough == ("--add-dir", "/foo")


def test_split_passthrough_with_prompt_file() -> None:
    cleaned, passthrough = _split_spawn_args([
        "spawn",
        "--prompt-file",
        "plan.md",
        "--",
        "--add-dir",
        "/foo",
    ])

    assert cleaned == ["spawn", "--prompt-file", "plan.md"]
    assert passthrough == ("--add-dir", "/foo")


def test_split_passthrough_without_separator() -> None:
    cleaned, passthrough = _split_spawn_args(["spawn", "-p", "hello"])

    assert cleaned == ["spawn", "-p", "hello"]
    assert passthrough == ()


def test_global_agent_flag_forces_agent_mode_without_profile_disambiguation() -> None:
    cleaned, options = cli_main._extract_global_options(["--agent", "coder", "--dry-run"])

    assert cleaned == ["coder", "--dry-run"]
    assert options.force_agent is True


def test_agent_flag_before_command_forces_agent_mode() -> None:
    cleaned, options = cli_main._extract_global_options(["--agent", "spawn", "list"])

    assert cleaned == ["spawn", "list"]
    assert options.force_agent is True


def test_post_command_agent_flag_is_preserved_as_spawn_profile_selection() -> None:
    cleaned, options = cli_main._extract_global_options(["spawn", "--agent", "coder"])

    assert cleaned == ["spawn", "-a", "coder"]
    assert options.force_agent is False


def test_split_passthrough_with_empty_tail() -> None:
    cleaned, passthrough = _split_spawn_args(["spawn", "-p", "hello", "--"])

    assert cleaned == ["spawn", "-p", "hello"]
    assert passthrough == ()
