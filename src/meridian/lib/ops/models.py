"""Model catalog operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from meridian.lib.config.catalog import CatalogModel, load_model_catalog, resolve_model
from meridian.lib.ops.registry import OperationSpec, operation


@dataclass(frozen=True, slots=True)
class ModelsListInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class ModelsShowInput:
    model: str = ""
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class ModelsListOutput:
    models: tuple[CatalogModel, ...]


def _repo_root(repo_root: str | None) -> Path | None:
    if repo_root is None:
        return None
    return Path(repo_root).expanduser().resolve()


def models_list_sync(payload: ModelsListInput) -> ModelsListOutput:
    models = tuple(load_model_catalog(repo_root=_repo_root(payload.repo_root)))
    return ModelsListOutput(models=models)


def models_show_sync(payload: ModelsShowInput) -> CatalogModel:
    model_name = payload.model.strip()
    if not model_name:
        raise ValueError("Model identifier must not be empty.")
    return resolve_model(model_name, repo_root=_repo_root(payload.repo_root))


async def models_list(payload: ModelsListInput) -> ModelsListOutput:
    return models_list_sync(payload)


async def models_show(payload: ModelsShowInput) -> CatalogModel:
    return models_show_sync(payload)


operation(
    OperationSpec[ModelsListInput, ModelsListOutput](
        name="models.list",
        handler=models_list,
        sync_handler=models_list_sync,
        input_type=ModelsListInput,
        output_type=ModelsListOutput,
        cli_group="models",
        cli_name="list",
        mcp_name="models_list",
        description="List catalog models with routing guidance.",
    )
)

operation(
    OperationSpec[ModelsShowInput, CatalogModel](
        name="models.show",
        handler=models_show,
        sync_handler=models_show_sync,
        input_type=ModelsShowInput,
        output_type=CatalogModel,
        cli_group="models",
        cli_name="show",
        mcp_name="models_show",
        description="Show one model by id or alias.",
    )
)
