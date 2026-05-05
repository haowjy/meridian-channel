"""Permanent regression guardrails for startup redesign boundaries."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from meridian.cli.startup.catalog import COMMAND_CATALOG
from meridian.cli.startup.classify import classify_invocation
from meridian.cli.startup.policy import StartupClass, StateRequirement, TelemetryMode


@pytest.mark.parametrize(
    ("argv", "expected_class", "expected_state_req", "expected_telemetry"),
    [
        # Root help/version are handled by entrypoint fast paths.
        (["--help"], None, None, None),
        (["-h"], None, None, None),
        (["--version"], None, None, None),
        # Primary launch.
        ([], StartupClass.PRIMARY_LAUNCH, StateRequirement.RUNTIME_WRITE, TelemetryMode.SEGMENT),
        (
            ["-m", "gpt"],
            StartupClass.PRIMARY_LAUNCH,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
        (
            ["--continue", "c123"],
            StartupClass.PRIMARY_LAUNCH,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
        # Read-only commands install no telemetry and require no writes.
        (
            ["spawn", "list"],
            StartupClass.READ_RUNTIME,
            StateRequirement.RUNTIME_READ,
            TelemetryMode.NONE,
        ),
        (
            ["spawn", "show", "p1"],
            StartupClass.READ_RUNTIME,
            StateRequirement.RUNTIME_READ,
            TelemetryMode.NONE,
        ),
        (
            ["work", "current"],
            StartupClass.READ_RUNTIME,
            StateRequirement.RUNTIME_READ,
            TelemetryMode.NONE,
        ),
        (
            ["config", "show"],
            StartupClass.READ_PROJECT,
            StateRequirement.PROJECT_READ,
            TelemetryMode.NONE,
        ),
        (
            ["init"],
            StartupClass.WRITE_PROJECT,
            StateRequirement.PROJECT_WRITE,
            TelemetryMode.SEGMENT_OPTIONAL,
        ),
        # Write commands use segment telemetry.
        (
            ["spawn", "create", "-p", "hello"],
            StartupClass.WRITE_RUNTIME,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
        (
            ["work", "start", "my-item"],
            StartupClass.WRITE_RUNTIME,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
        # Deep command paths.
        (
            ["spawn", "report", "show", "p1"],
            StartupClass.READ_RUNTIME,
            StateRequirement.RUNTIME_READ,
            TelemetryMode.NONE,
        ),
        (
            ["spawn", "report", "search", "query"],
            StartupClass.READ_RUNTIME,
            StateRequirement.RUNTIME_READ,
            TelemetryMode.NONE,
        ),
        # Service classes.
        (
            ["chat"],
            StartupClass.SERVICE_RUNTIME,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
        (
            ["chat", "ls"],
            StartupClass.CLIENT_READ,
            StateRequirement.RUNTIME_READ,
            TelemetryMode.NONE,
        ),
        (["serve"], StartupClass.SERVICE_ROOTLESS, StateRequirement.NONE, TelemetryMode.STDERR),
        # Trivial paths.
        (
            ["mars", "models", "list"],
            StartupClass.TRIVIAL,
            StateRequirement.NONE,
            TelemetryMode.NONE,
        ),
        (["completion", "bash"], StartupClass.TRIVIAL, StateRequirement.NONE, TelemetryMode.NONE),
        # Redirects.
        (["models", "list"], StartupClass.TRIVIAL, StateRequirement.NONE, TelemetryMode.NONE),
        # Default route: spawn with only options classifies as spawn create.
        (
            ["spawn", "-p", "hello"],
            StartupClass.WRITE_RUNTIME,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
        # Passthrough arguments do not affect classification.
        (
            ["spawn", "create", "--", "extra"],
            StartupClass.WRITE_RUNTIME,
            StateRequirement.RUNTIME_WRITE,
            TelemetryMode.SEGMENT,
        ),
    ],
)
def test_classifier_contract(
    argv: list[str],
    expected_class: StartupClass | None,
    expected_state_req: StateRequirement | None,
    expected_telemetry: TelemetryMode | None,
) -> None:
    descriptor = classify_invocation(argv, COMMAND_CATALOG)
    if expected_class is None:
        assert descriptor is None
    else:
        assert descriptor is not None
        assert descriptor.startup_class == expected_class
        assert descriptor.state_requirement == expected_state_req
        assert descriptor.telemetry_mode == expected_telemetry


@contextmanager
def _isolated_meridian_modules() -> Iterator[None]:
    """Temporarily clear Meridian modules and restore them after the assertion.

    Import-boundary tests need a cold import surface, but permanently deleting
    Meridian modules from ``sys.modules`` contaminates later tests that hold
    references to already-imported module objects.
    """

    saved = {
        module_name: module
        for module_name, module in sys.modules.items()
        if module_name == "meridian" or module_name.startswith("meridian.")
    }
    for module_name in tuple(saved):
        del sys.modules[module_name]
    try:
        yield
    finally:
        for module_name in tuple(sys.modules):
            if module_name == "meridian" or module_name.startswith("meridian."):
                del sys.modules[module_name]
        sys.modules.update(saved)


def test_startup_catalog_does_not_import_ops() -> None:
    """Startup catalog must be import-cheap."""
    with _isolated_meridian_modules():
        modules_before = set(sys.modules)

        importlib.import_module("meridian.cli.startup.catalog")

        new_modules = set(sys.modules) - modules_before
        forbidden = {"meridian.lib.ops", "meridian.lib.harness", "meridian.server"}
        for module_name in new_modules:
            for forbidden_prefix in forbidden:
                assert not module_name.startswith(forbidden_prefix), (
                    f"startup.catalog transitively imported {module_name}"
                )


def test_entrypoint_does_not_import_main_at_module_scope() -> None:
    """Entrypoint must be import-cheap."""
    with _isolated_meridian_modules():
        modules_before = set(sys.modules)

        importlib.import_module("meridian.cli.entrypoint")

        new_modules = set(sys.modules) - modules_before
        assert "meridian.cli.main" not in new_modules


def test_catalog_covers_all_top_level_commands() -> None:
    """Every top-level command in the app tree has a catalog descriptor."""
    from meridian.cli.app_tree import app

    app_commands = {name for name in app.resolved_commands() if not name.startswith("-")}
    catalog_names = COMMAND_CATALOG.top_level_names()

    missing = app_commands - catalog_names
    assert not missing, f"Commands in app tree but missing from catalog: {missing}"
