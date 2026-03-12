"""CLI command handlers for agents.* operations."""


from collections.abc import Callable
from functools import partial
from typing import Any

from meridian.lib.ops.manifest import get_operations_for_surface
from meridian.lib.ops.catalog import (
    AgentsListInput,
    agents_list_sync,
)

Emitter = Callable[[Any], None]


def _agents_list(emit: Emitter) -> None:
    emit(agents_list_sync(AgentsListInput()))


def register_agents_commands(app: Any, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "agents.list": lambda: partial(_agents_list, emit),
    }

    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_operations_for_surface("cli"):
        if op.cli_group != "agents":
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(f"No CLI handler registered for operation '{op.name}'")
        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"
        app.command(handler, name=op.cli_name, help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    return registered, descriptions
