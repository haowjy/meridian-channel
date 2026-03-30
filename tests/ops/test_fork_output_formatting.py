import importlib

from meridian.lib.ops.spawn.models import SpawnActionOutput

main_cli = importlib.import_module("meridian.cli.main")


def test_primary_launch_output_formats_fork_resume_human_text() -> None:
    output = main_cli.PrimaryLaunchOutput(
        message="Session forked.",
        exit_code=0,
        forked_from="c367",
        resume_command="meridian --continue c402",
    )

    rendered = output.format_text()
    assert "Session forked from c367." in rendered
    assert "meridian --continue c402" in rendered


def test_primary_launch_output_formats_fork_dry_run_human_text() -> None:
    output = main_cli.PrimaryLaunchOutput(
        message="Fork dry-run.",
        exit_code=0,
        command=("meridian", "--fork", "c367", "--dry-run"),
        forked_from="c367",
    )

    rendered = output.format_text()
    assert "Fork dry-run. (from c367)" in rendered
    assert "meridian --fork c367 --dry-run" in rendered


def test_spawn_action_output_includes_forked_from_in_wire_and_text() -> None:
    output = SpawnActionOutput(
        command="spawn.create",
        status="dry-run",
        message="Dry run complete.",
        forked_from="c367",
        cli_command=("meridian", "spawn", "--fork", "c367", "-p", "branch"),
    )

    wire = output.to_wire()
    assert wire["forked_from"] == "c367"

    rendered = output.format_text()
    assert "Forked from: c367" in rendered
    assert "meridian spawn --fork c367 -p branch" in rendered
