"""Shared CLI command registration from the operation manifest."""

from collections.abc import Callable

from cyclopts import App

from meridian.lib.ops.manifest import get_operations_for_surface

HandlerFactory = Callable[[], Callable[..., None]]


def register_manifest_cli_group(
    app: App,
    *,
    group: str,
    handlers: dict[str, HandlerFactory],
    default_handler: Callable[..., None] | None = None,
) -> tuple[set[str], dict[str, str]]:
    """Register CLI commands for one manifest group."""
    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_operations_for_surface("cli"):
        if op.cli_group != group:
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(f"No CLI handler registered for operation {op.name}")
        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"
        app.command(handler, name=op.cli_name, help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    if default_handler is not None:
        app.default(default_handler)

    return registered, descriptions
