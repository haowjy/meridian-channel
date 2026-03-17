"""Alias parsing and merge helpers for the model catalog."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from meridian.lib.catalog.model_policy import DEFAULT_HARNESS_PATTERNS, route_model_with_patterns
from meridian.lib.catalog.models_toml import catalog_path, load_models_file_payload
from meridian.lib.core.types import HarnessId, ModelId

_DEFAULT_ALIASES_RESOURCE = "default-aliases.toml"


class AliasEntry(BaseModel):
    """Alias entry for model lookup + operator-facing guidance."""

    model_config = ConfigDict(frozen=True)

    alias: str
    model_id: ModelId
    role: str | None = None
    strengths: str | None = None
    resolved_harness: HarnessId | None = Field(default=None, exclude=True)

    @property
    def harness(self) -> HarnessId:
        if self.resolved_harness is not None:
            return self.resolved_harness
        return route_model_with_patterns(
            str(self.model_id),
            patterns_by_harness=DEFAULT_HARNESS_PATTERNS,
        ).harness_id

    def format_text(self, ctx: object | None = None) -> str:
        _ = ctx
        from meridian.cli.format_helpers import kv_block

        pairs: list[tuple[str, str | None]] = [
            ("Model", str(self.model_id)),
            ("Harness", str(self.harness)),
            ("Alias", self.alias or None),
            ("Role", self.role or None),
            ("Strengths", self.strengths or None),
        ]
        return kv_block(pairs)


def entry(*, alias: str, model_id: str, role: str | None, strengths: str | None) -> AliasEntry:
    return AliasEntry(
        alias=alias,
        model_id=ModelId(model_id),
        role=role,
        strengths=strengths,
    )


def load_builtin_aliases() -> list[AliasEntry]:
    resource_path = Path(
        str(importlib.resources.files("meridian.resources") / _DEFAULT_ALIASES_RESOURCE)
    )
    entries = _load_aliases_from_payload(load_models_file_payload(resource_path))
    return [entries[key] for key in sorted(entries)]


def load_user_aliases(repo_root: Path) -> list[AliasEntry]:
    path = catalog_path(repo_root)
    if not path.is_file():
        return []

    entries = _load_aliases_from_payload(load_models_file_payload(path))
    return [entries[key] for key in sorted(entries)]


def merge_alias_entries(
    builtin_aliases: list[AliasEntry],
    user_aliases: list[AliasEntry],
) -> list[AliasEntry]:
    merged: dict[str, AliasEntry] = {item.alias: item for item in builtin_aliases}
    for item in user_aliases:
        merged[item.alias] = item
    return [merged[key] for key in sorted(merged)]


def load_alias_by_name(name: str, aliases: list[AliasEntry]) -> AliasEntry | None:
    normalized = name.strip()
    if not normalized:
        return None
    for entry in aliases:
        if entry.alias == normalized:
            return entry
    return None


def _load_aliases_from_payload(payload: dict[str, object]) -> dict[str, AliasEntry]:
    metadata = _coerce_metadata_map(payload.get("metadata"))
    return _coerce_alias_entries(payload.get("aliases"), metadata=metadata)


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
            aliases[alias] = entry(
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
                continue
            aliases[alias] = entry(
                alias=alias,
                model_id=model_id,
                role=_coerce_string(table.get("role")) or None,
                strengths=_coerce_string(table.get("strengths")) or None,
            )
        # invalid rows are ignored to match prior behavior
    return aliases


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


def _coerce_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
