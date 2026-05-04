"""Contract tests for startup-cheap CLI invocation classification."""

from meridian.cli.startup.catalog import COMMAND_CATALOG
from meridian.cli.startup.classify import classify_invocation
from meridian.cli.startup.policy import StartupClass


def _path(argv: list[str]) -> tuple[str, ...] | None:
    descriptor = classify_invocation(argv, COMMAND_CATALOG)
    if descriptor is None:
        return None
    return descriptor.command_path


def test_root_help_is_trivial_entrypoint_path() -> None:
    assert classify_invocation(["--help"], COMMAND_CATALOG) is None


def test_spawn_list_classifies_as_spawn_list_descriptor() -> None:
    assert _path(["spawn", "list"]) == ("spawn", "list")


def test_deep_spawn_report_show_path_is_first_class() -> None:
    assert _path(["spawn", "report", "show"]) == ("spawn", "report", "show")


def test_spawn_default_route_classifies_as_create_descriptor() -> None:
    assert _path(["spawn", "-m", "gpt", "-p", "hello"]) == ("spawn",)


def test_chat_ls_is_client_read_not_interactive_service() -> None:
    descriptor = classify_invocation(["chat", "ls"], COMMAND_CATALOG)

    assert descriptor is not None
    assert descriptor.command_path == ("chat", "ls")
    assert descriptor.startup_class is StartupClass.CLIENT_READ


def test_chat_without_subcommand_is_service_runtime() -> None:
    descriptor = classify_invocation(["chat"], COMMAND_CATALOG)

    assert descriptor is not None
    assert descriptor.command_path == ("chat",)
    assert descriptor.startup_class is StartupClass.SERVICE_RUNTIME


def test_models_list_descriptor_owns_redirect_policy() -> None:
    descriptor = classify_invocation(["models", "list"], COMMAND_CATALOG)

    assert descriptor is not None
    assert descriptor.command_path == ("models", "list")
    assert descriptor.redirect is not None
    assert descriptor.redirect.target == "mars models list"


def test_lone_harness_shortcut_remains_primary_launch_path() -> None:
    assert classify_invocation(["claude"], COMMAND_CATALOG) is None


def test_passthrough_tokens_do_not_affect_classification() -> None:
    assert _path(["spawn", "create", "--", "extra"]) == ("spawn", "create")


def test_unknown_command_is_not_classified_as_root() -> None:
    assert classify_invocation(["does-not-exist"], COMMAND_CATALOG) is None
