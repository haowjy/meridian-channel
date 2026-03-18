"""Alias parsing and merge helpers for the model catalog."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

from pydantic import BaseModel, ConfigDict, Field

from meridian.lib.catalog.model_policy import DEFAULT_HARNESS_PATTERNS, route_model_with_patterns
from meridian.lib.catalog.models_toml import catalog_path, load_models_file_payload
from meridian.lib.core.types import HarnessId, ModelId

if TYPE_CHECKING:
    from meridian.lib.catalog.models import DiscoveredModel


class _AliasSpec(NamedTuple):
    provider: str
    include: str
    exclude: tuple[str, ...]


_BUILTIN_ALIAS_SPECS: dict[str, _AliasSpec] = {
    "opus": _AliasSpec("anthropic", "opus", ()),
    "sonnet": _AliasSpec("anthropic", "sonnet", ()),
    "haiku": _AliasSpec("anthropic", "haiku", ()),
    "codex": _AliasSpec("openai", "codex", ("-mini", "-spark", "-max")),
    "gpt": _AliasSpec("openai", "gpt-", ("-codex", "-pro", "-mini", "-nano", "-chat", "-turbo")),
    "gemini": _AliasSpec("google", "pro", ("-customtools",)),
}

_FALLBACK_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
    "codex": "gpt-5.3-codex",
    "gpt": "gpt-5.4",
    "gemini": "gemini-3.1-pro-preview",
}


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


def _resolve_alias_from_models(
    spec: _AliasSpec,
    models: Sequence[DiscoveredModel],
) -> str | None:
    candidates: list[DiscoveredModel] = []
    for m in models:
        if m.provider != spec.provider:
            continue
        mid = m.id.lower()
        if spec.include not in mid:
            continue
        if mid.endswith("-latest"):
            continue
        if any(excl in mid for excl in spec.exclude):
            continue
        candidates.append(m)

    if not candidates:
        return None

    # Latest date first; for same date, prefer shorter (cleaner) ID
    candidates.sort(key=lambda m: (m.release_date or "", -len(m.id)), reverse=True)
    return candidates[0].id


def load_builtin_aliases(
    discovered_models: Sequence[DiscoveredModel] | None = None,
) -> list[AliasEntry]:
    resolved: dict[str, str] = {}
    if discovered_models:
        for alias, spec in _BUILTIN_ALIAS_SPECS.items():
            model_id = _resolve_alias_from_models(spec, discovered_models)
            if model_id is not None:
                resolved[alias] = model_id

    # Fill gaps from fallbacks
    for alias, model_id in _FALLBACK_ALIASES.items():
        if alias not in resolved:
            resolved[alias] = model_id

    return [
        entry(alias=a, model_id=mid, role=None, strengths=None)
        for a, mid in sorted(resolved.items())
    ]


def load_user_aliases(
    repo_root: Path,
    discovered_models: Sequence[DiscoveredModel] | None = None,
) -> list[AliasEntry]:
    path = catalog_path(repo_root)
    if not path.is_file():
        return []

    payload = load_models_file_payload(path)
    pinned = _load_aliases_from_payload(payload)

    if discovered_models:
        specs = _coerce_user_alias_specs(payload.get("aliases"))
        for alias, spec in specs.items():
            if alias not in pinned:
                model_id = _resolve_alias_from_models(spec, discovered_models)
                if model_id is not None:
                    pinned[alias] = entry(
                        alias=alias, model_id=model_id, role=None, strengths=None
                    )

    return [pinned[key] for key in sorted(pinned)]


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
            # Skip auto-resolve specs (tables with provider + include)
            if _coerce_string(table.get("provider")) and _coerce_string(table.get("include")):
                continue
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


def _coerce_user_alias_specs(raw_aliases: object) -> dict[str, _AliasSpec]:
    if not isinstance(raw_aliases, dict):
        return {}

    specs: dict[str, _AliasSpec] = {}
    for raw_alias, raw_value in cast("dict[object, object]", raw_aliases).items():
        alias = _coerce_string(raw_alias)
        if alias is None or not isinstance(raw_value, dict):
            continue
        table = cast("dict[object, object]", raw_value)
        provider = _coerce_string(table.get("provider"))
        include = _coerce_string(table.get("include"))
        if provider is None or include is None:
            continue
        raw_exclude = table.get("exclude")
        exclude: tuple[str, ...] = ()
        if isinstance(raw_exclude, list):
            exclude = tuple(
                s
                for item in cast("list[object]", raw_exclude)
                if isinstance(item, str)
                for s in [item.strip()]
                if s
            )
        specs[alias] = _AliasSpec(provider=provider, include=include, exclude=exclude)
    return specs


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
