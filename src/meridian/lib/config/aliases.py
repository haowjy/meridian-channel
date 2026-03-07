"""Alias-first model resolution backed by built-in + user alias files."""

from __future__ import annotations

import importlib.resources
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from meridian.lib.config._paths import resolve_repo_root
from meridian.lib.config.routing import route_model
from meridian.lib.state.paths import resolve_state_paths
from meridian.lib.types import HarnessId, ModelId

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext

logger = logging.getLogger(__name__)

_DEFAULT_ALIASES_RESOURCE = "default-aliases.toml"


@dataclass(frozen=True, slots=True)
class AliasEntry:
    """Alias entry for model lookup + operator-facing guidance."""

    alias: str
    model_id: ModelId
    role: str | None = None
    strengths: str | None = None

    @property
    def harness(self) -> HarnessId:
        """Harness inferred from the model identifier via prefix routing."""

        return route_model(str(self.model_id)).harness_id

    @property
    def cost_tier(self) -> str:
        """Backward-compatible catalog field retained for tabular output."""

        return ""

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Key-value detail view for a single alias entry."""
        from meridian.cli.format_helpers import kv_block

        pairs: list[tuple[str, str | None]] = [
            ("Model", str(self.model_id)),
            ("Harness", str(self.harness)),
            ("Alias", self.alias or None),
            ("Role", self.role or None),
            ("Strengths", self.strengths or None),
        ]
        return kv_block(pairs)


# Backward-compatible export name.
CatalogModel = AliasEntry


def _catalog_path(repo_root: Path) -> Path:
    return resolve_state_paths(repo_root).models_path


def _coerce_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_metadata_map(raw_metadata: object) -> dict[str, dict[str, str]]:
    if not isinstance(raw_metadata, dict):
        return {}

    metadata: dict[str, dict[str, str]] = {}
    for raw_alias, raw_row in cast("dict[object, object]", raw_metadata).items():
        alias = _coerce_string(raw_alias)
        if alias is None or not isinstance(raw_row, dict):
            continue
        row = cast("dict[object, object]", raw_row)
        metadata[alias] = {
            "role": _coerce_string(row.get("role")) or "",
            "strengths": _coerce_string(row.get("strengths")) or "",
        }
    return metadata


def _entry(*, alias: str, model_id: str, role: str | None, strengths: str | None) -> AliasEntry:
    return AliasEntry(
        alias=alias,
        model_id=ModelId(model_id),
        role=role,
        strengths=strengths,
    )


def _coerce_alias_entries(
    raw_aliases: object,
    *,
    metadata: dict[str, dict[str, str]],
) -> dict[str, AliasEntry]:
    if not isinstance(raw_aliases, dict):
        return {}

    aliases: dict[str, AliasEntry] = {}
    for raw_alias, raw_value in cast("dict[object, object]", raw_aliases).items():
        alias = _coerce_string(raw_alias)
        if alias is None:
            continue

        meta_row = metadata.get(alias, {})

        if isinstance(raw_value, str):
            model_id = _coerce_string(raw_value)
            if model_id is None:
                continue
            aliases[alias] = _entry(
                alias=alias,
                model_id=model_id,
                role=meta_row.get("role") or None,
                strengths=meta_row.get("strengths") or None,
            )
            continue

        if isinstance(raw_value, dict):
            table = cast("dict[object, object]", raw_value)
            model_id = _coerce_string(table.get("model_id") or table.get("id"))
            if model_id is None:
                logger.warning("Ignoring alias '%s' without model_id.", alias)
                continue
            aliases[alias] = _entry(
                alias=alias,
                model_id=model_id,
                role=_coerce_string(table.get("role")) or None,
                strengths=_coerce_string(table.get("strengths")) or None,
            )
            continue

        logger.warning("Ignoring invalid alias entry '%s'.", alias)

    return aliases


def _load_alias_file(path: Path) -> dict[str, AliasEntry]:
    payload_obj = tomllib.loads(path.read_text(encoding="utf-8"))
    payload = cast("dict[str, object]", payload_obj)

    metadata = _coerce_metadata_map(payload.get("metadata"))
    return _coerce_alias_entries(payload.get("aliases"), metadata=metadata)


def load_builtin_aliases() -> list[AliasEntry]:
    """Load built-in aliases bundled with meridian."""

    resource_path = Path(
        str(importlib.resources.files("meridian.resources") / _DEFAULT_ALIASES_RESOURCE)
    )
    entries = _load_alias_file(resource_path)
    return [entries[key] for key in sorted(entries)]


def load_user_aliases(repo_root: Path | None = None) -> list[AliasEntry]:
    """Load user-defined aliases from `.meridian/models.toml [aliases]`."""

    root = resolve_repo_root(repo_root)
    path = _catalog_path(root)
    if not path.is_file():
        return []

    entries = _load_alias_file(path)
    return [entries[key] for key in sorted(entries)]


def load_merged_aliases(repo_root: Path | None = None) -> list[AliasEntry]:
    """Load built-in aliases merged with user aliases (user wins by alias key)."""

    merged: dict[str, AliasEntry] = {entry.alias: entry for entry in load_builtin_aliases()}
    for entry in load_user_aliases(repo_root=repo_root):
        merged[entry.alias] = entry
    return [merged[key] for key in sorted(merged)]


def resolve_alias(name: str, repo_root: Path | None = None) -> ModelId | None:
    """Resolve one alias to a model identifier."""

    normalized = name.strip()
    if not normalized:
        return None

    for entry in load_merged_aliases(repo_root=repo_root):
        if entry.alias == normalized:
            return entry.model_id
    return None


# Backward-compatible export name.
def load_model_catalog(repo_root: Path | None = None) -> list[AliasEntry]:
    return load_merged_aliases(repo_root=repo_root)


def resolve_model(name_or_alias: str, repo_root: Path | None = None) -> AliasEntry:
    """Resolve alias to model id, or pass through a direct model identifier."""

    normalized = name_or_alias.strip()
    if not normalized:
        raise ValueError("Model identifier must not be empty.")

    aliases = load_merged_aliases(repo_root=repo_root)
    by_alias = {entry.alias: entry for entry in aliases}
    resolved = by_alias.get(normalized)
    if resolved is not None:
        # Validate alias targets through routing to preserve prior behavior.
        _ = route_model(str(resolved.model_id))
        return resolved

    _ = route_model(normalized)
    return AliasEntry(alias="", model_id=ModelId(normalized), role=None, strengths=None)
