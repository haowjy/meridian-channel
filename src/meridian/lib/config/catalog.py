"""Built-in model catalog and user overrides."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from meridian.lib.config._paths import resolve_repo_root
from meridian.lib.config.routing import route_model
from meridian.lib.types import HarnessId, ModelId

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogModel:
    """Catalog entry for a model + operational guidance."""

    model_id: ModelId
    aliases: tuple[str, ...]
    role: str
    strengths: str
    cost_tier: str
    harness: HarnessId

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Key-value detail view for a single model."""
        from meridian.cli.format_helpers import kv_block

        pairs: list[tuple[str, str | None]] = [
            ("Model", str(self.model_id)),
            ("Harness", str(self.harness)),
            ("Aliases", ", ".join(self.aliases) if self.aliases else None),
            ("Role", self.role),
            ("Strengths", self.strengths),
            ("Cost", self.cost_tier),
        ]
        return kv_block(pairs)


def _entry(
    model_id: str,
    aliases: tuple[str, ...],
    role: str,
    strengths: str,
    cost_tier: str,
) -> CatalogModel:
    routing = route_model(model_id)
    return CatalogModel(
        model_id=ModelId(model_id),
        aliases=aliases,
        role=role,
        strengths=strengths,
        cost_tier=cost_tier,
        harness=routing.harness_id,
    )


def builtin_model_catalog() -> tuple[CatalogModel, ...]:
    """Return built-in model catalog shipped with meridian."""

    return (
        _entry(
            model_id="claude-opus-4-6",
            aliases=("opus",),
            role="Default / all-rounder",
            strengths="Best supervisor brain",
            cost_tier="$$$",
        ),
        _entry(
            model_id="gpt-5.3-codex",
            aliases=("codex",),
            role="Executor / correctness",
            strengths="Repo implementation and correctness passes",
            cost_tier="$",
        ),
        _entry(
            model_id="claude-sonnet-4-6",
            aliases=("sonnet",),
            role="Fast generalist",
            strengths="UI iteration and fast implementation",
            cost_tier="$$",
        ),
        _entry(
            model_id="claude-haiku-4-5",
            aliases=("haiku",),
            role="Quick transforms",
            strengths="Commit messages and quick transforms",
            cost_tier="$",
        ),
        _entry(
            model_id="gpt-5.2-high",
            aliases=("gpt52h",),
            role="Escalation solver",
            strengths="Strong generalist reasoning plus coding",
            cost_tier="$$",
        ),
        _entry(
            model_id="gemini-3.1-pro",
            aliases=("gemini",),
            role="Researcher / multimodal",
            strengths="Knowledge breadth and multimodal tasks",
            cost_tier="$$",
        ),
    )


def _catalog_path(repo_root: Path) -> Path:
    return repo_root / ".meridian" / "models.toml"


def _parse_aliases(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        candidate = raw.strip()
        return (candidate,) if candidate else ()
    if isinstance(raw, list):
        values: list[str] = []
        seen: set[str] = set()
        for item in cast("list[object]", raw):
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(normalized)
        return tuple(values)
    return ()


def _parse_override_row(source_key: str, row: dict[str, object]) -> CatalogModel:
    model_key = str(row.get("model_id") or row.get("id") or source_key).strip()
    if not model_key:
        raise ValueError("Model override row is missing `model_id` (or `id`).")

    role = str(row.get("role") or "Custom model").strip()
    strengths = str(row.get("strengths") or "").strip()
    cost_tier = str(row.get("cost_tier") or "$$").strip()
    harness_text = str(row.get("harness") or "").strip()
    harness = HarnessId(harness_text) if harness_text else route_model(model_key).harness_id

    return CatalogModel(
        model_id=ModelId(model_key),
        aliases=_parse_aliases(row.get("aliases")),
        role=role,
        strengths=strengths,
        cost_tier=cost_tier,
        harness=harness,
    )


def _load_overrides(path: Path) -> tuple[CatalogModel, ...]:
    if not path.is_file():
        return ()
    payload_obj = tomllib.loads(path.read_text(encoding="utf-8"))
    payload = cast("dict[str, object]", payload_obj)
    raw_models = payload.get("models")
    if raw_models is None:
        return ()

    parsed: list[CatalogModel] = []
    if isinstance(raw_models, list):
        for row in cast("list[object]", raw_models):
            if isinstance(row, dict):
                parsed.append(_parse_override_row("", cast("dict[str, object]", row)))
        return tuple(parsed)

    if isinstance(raw_models, dict):
        for key, row in cast("dict[object, object]", raw_models).items():
            if isinstance(row, dict):
                parsed.append(_parse_override_row(str(key), cast("dict[str, object]", row)))
        return tuple(parsed)

    return ()


def load_model_catalog(repo_root: Path | None = None) -> list[CatalogModel]:
    """Load built-in model catalog with optional `.meridian/models.toml` overrides."""

    root = resolve_repo_root(repo_root)
    merged: dict[str, CatalogModel] = {
        str(entry.model_id): entry for entry in builtin_model_catalog()
    }
    for entry in _load_overrides(_catalog_path(root)):
        merged[str(entry.model_id)] = entry
    return [merged[key] for key in sorted(merged)]


def resolve_model(name_or_alias: str, repo_root: Path | None = None) -> CatalogModel:
    """Resolve model by ID or alias from merged catalog."""

    normalized = name_or_alias.strip()
    if not normalized:
        raise ValueError("Model identifier must not be empty.")

    catalog = load_model_catalog(repo_root=repo_root)
    by_id = {str(entry.model_id): entry for entry in catalog}
    if normalized in by_id:
        return by_id[normalized]

    alias_to_model: dict[str, CatalogModel] = {}
    for entry in catalog:
        for alias in entry.aliases:
            existing = alias_to_model.get(alias)
            if existing is None:
                alias_to_model[alias] = entry
                continue
            if str(existing.model_id) == str(entry.model_id):
                continue
            logger.warning(
                "Model alias '%s' is declared by '%s' and '%s'. Using '%s'.",
                alias,
                existing.model_id,
                entry.model_id,
                existing.model_id,
            )

    resolved = alias_to_model.get(normalized)
    if resolved is None:
        raise KeyError(f"Unknown model '{name_or_alias}'.")
    return resolved
