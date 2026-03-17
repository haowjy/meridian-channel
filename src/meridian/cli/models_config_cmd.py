"""CLI command handlers for models config operations."""

from collections.abc import Callable
from functools import partial
from typing import Any

from cyclopts import App

from meridian.lib.ops.models_config import (
    ModelsConfigGetInput,
    ModelsConfigInitInput,
    ModelsConfigResetInput,
    ModelsConfigSetInput,
    ModelsConfigShowInput,
    models_config_get_sync,
    models_config_init_sync,
    models_config_reset_sync,
    models_config_set_sync,
    models_config_show_sync,
)

Emitter = Callable[[Any], None]


def _models_config_init(emit: Emitter) -> None:
    emit(models_config_init_sync(ModelsConfigInitInput()))


def _models_config_show(emit: Emitter) -> None:
    emit(models_config_show_sync(ModelsConfigShowInput()))


def _models_config_get(emit: Emitter, key: str) -> None:
    emit(models_config_get_sync(ModelsConfigGetInput(key=key)))


def _models_config_set(emit: Emitter, key: str, value: str) -> None:
    emit(models_config_set_sync(ModelsConfigSetInput(key=key, value=value)))


def _models_config_reset(emit: Emitter, key: str) -> None:
    emit(models_config_reset_sync(ModelsConfigResetInput(key=key)))


def register_models_config_commands(app: App, emit: Emitter) -> None:
    app.command(
        partial(_models_config_init, emit),
        name="init",
        help="Scaffold .meridian/models.toml.",
    )
    app.command(
        partial(_models_config_show, emit),
        name="show",
        help="Show .meridian/models.toml.",
    )
    app.command(
        partial(_models_config_get, emit),
        name="get",
        help="Read one key from .meridian/models.toml.",
    )
    app.command(
        partial(_models_config_set, emit),
        name="set",
        help="Set one key in .meridian/models.toml using a TOML literal value.",
    )
    app.command(
        partial(_models_config_reset, emit),
        name="reset",
        help="Remove one key from .meridian/models.toml.",
    )
