"""CLI command handlers for agents.* operations."""


from collections.abc import Callable
from functools import partial
from typing import Any

from meridian.cli.registration import register_manifest_cli_group
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
    return register_manifest_cli_group(app, group="agents", handlers=handlers)
