"""Model routing, discovery, alias resolution, and catalog."""

import fnmatch
import importlib.resources
import json
import logging
import os
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Literal, cast
from urllib import request
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from meridian.lib.config.settings import resolve_repo_root
from meridian.lib.core.types import HarnessId, ModelId
from meridian.lib.core.util import FormatContext
from meridian.lib.state.paths import resolve_cache_dir, resolve_state_paths

logger = logging.getLogger(__name__)


# ─── Routing ───────────────────────────────────────────────────────────

SpawnMode = Literal["harness", "direct"]


class RoutingDecision(BaseModel):
    """Routing result for a model selection request."""

    model_config = ConfigDict(frozen=True)

    harness_id: HarnessId
    warning: str | None = None


_DEFAULT_HARNESS_PATTERNS: dict[HarnessId, tuple[str, ...]] = {
    HarnessId.CLAUDE: ("claude-*", "opus*", "sonnet*", "haiku*"),
    HarnessId.CODEX: ("gpt-*", "o1*", "o3*", "o4*", "codex*"),
    HarnessId.OPENCODE: ("opencode-*", "gemini*", "*/*"),
}


class ModelVisibilityConfig(BaseModel):
    """Default-list visibility policy for `meridian models list`."""

    model_config = ConfigDict(frozen=True)

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = (
        "*-latest",
        "*-deep-research",
        "gemini-live-*",
        "o1*",
        "o3*",
        "o4*",
    )
    max_input_cost: float | None = 10.0
    max_age_days: int | None = 180
    hide_date_variants: bool = True


_DEFAULT_MODEL_VISIBILITY = ModelVisibilityConfig()


def _match_pattern(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value, pattern)


def _coerce_pattern_list(raw_value: object, *, source: str) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        raise ValueError(f"Invalid value for '{source}': expected array of strings.")
    patterns: list[str] = []
    for raw_pattern in cast("list[object]", raw_value):
        if not isinstance(raw_pattern, str):
            raise ValueError(f"Invalid value for '{source}': expected array of strings.")
        pattern = raw_pattern.strip()
        if not pattern:
            raise ValueError(f"Invalid value for '{source}': empty pattern.")
        patterns.append(pattern)
    return tuple(patterns)


def _load_models_file_payload(path: Path) -> dict[str, object]:
    payload_obj = tomllib.loads(path.read_text(encoding="utf-8"))
    return cast("dict[str, object]", payload_obj)


def _load_user_harness_patterns(repo_root: Path | None = None) -> dict[HarnessId, tuple[str, ...]]:
    if repo_root is None:
        return {}

    path = _catalog_path(resolve_repo_root(repo_root))
    if not path.is_file():
        return {}

    payload = _load_models_file_payload(path)
    raw_section = payload.get("harness_patterns")
    if raw_section is None:
        return {}
    if not isinstance(raw_section, dict):
        raise ValueError("Invalid value for 'harness_patterns': expected table.")

    patterns_by_harness: dict[HarnessId, tuple[str, ...]] = {}
    for raw_harness, raw_patterns in cast("dict[object, object]", raw_section).items():
        if not isinstance(raw_harness, str):
            raise ValueError("Invalid value for 'harness_patterns': expected harness keys.")
        harness_name = raw_harness.strip()
        try:
            harness = HarnessId(harness_name)
        except ValueError as exc:
            raise ValueError(
                f"Invalid harness_patterns key '{raw_harness}'. "
                f"Expected one of: {', '.join(str(item) for item in HarnessId)}."
            ) from exc
        patterns_by_harness[harness] = _coerce_pattern_list(
            raw_patterns, source=f"harness_patterns.{harness_name}"
        )
    return patterns_by_harness


def load_harness_patterns(repo_root: Path | None = None) -> dict[HarnessId, tuple[str, ...]]:
    patterns = dict(_DEFAULT_HARNESS_PATTERNS)
    patterns.update(_load_user_harness_patterns(repo_root=repo_root))
    return patterns


def route_model(
    model: str,
    mode: SpawnMode = "harness",
    *,
    repo_root: Path | None = None,
) -> RoutingDecision:
    """Route a model ID to the corresponding harness family.

    Unknown model families are rejected to avoid silently choosing the wrong harness.
    """

    normalized = model.strip()
    if mode == "direct":
        return RoutingDecision(harness_id=HarnessId.DIRECT)

    matched_harnesses = [
        harness
        for harness, patterns in load_harness_patterns(repo_root=repo_root).items()
        if any(_match_pattern(pattern, normalized) for pattern in patterns)
    ]
    if len(matched_harnesses) == 1:
        return RoutingDecision(harness_id=matched_harnesses[0])
    if len(matched_harnesses) > 1:
        joined = ", ".join(str(harness) for harness in matched_harnesses)
        raise ValueError(
            f"Model '{model}' matches multiple harness_patterns entries: {joined}. "
            "Update .meridian/models.toml to disambiguate."
        )

    raise ValueError(
        f"Unknown model family '{model}'. Configure harness_patterns in .meridian/models.toml."
    )


# ─── Discovery ─────────────────────────────────────────────────────────

_MODELS_DEV_URL = "https://models.dev/api.json"
_REQUEST_TIMEOUT_SECONDS = 10
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_FILE_NAME = "models.json"
_PROVIDER_TO_HARNESS: dict[str, HarnessId] = {
    "anthropic": HarnessId.CLAUDE,
    "openai": HarnessId.CODEX,
    "google": HarnessId.OPENCODE,
}


class DiscoveredModel(BaseModel):
    """Normalized discovered model entry from models.dev."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    family: str
    provider: str
    harness: HarnessId
    cost_input: float | None
    cost_output: float | None
    context_limit: int | None
    output_limit: int | None
    capabilities: tuple[str, ...]
    release_date: str | None


def _parse_string(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _parse_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _parse_capabilities(value: object) -> tuple[str, ...]:
    raw_values: list[object]
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list):
        raw_values = cast("list[object]", value)
    elif isinstance(value, tuple):
        raw_values = list(cast("tuple[object, ...]", value))
    elif isinstance(value, set):
        raw_values = list(cast("set[object]", value))
    else:
        return ()

    capabilities: set[str] = set()
    for raw in raw_values:
        if not isinstance(raw, str):
            continue
        normalized = raw.strip().lower()
        if normalized:
            capabilities.add(normalized)
    return tuple(sorted(capabilities))


class _ModelsDevCost(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input: float | None = None
    output: float | None = None

    @field_validator("input", "output", mode="before")
    @classmethod
    def _parse_cost_value(cls, value: object) -> float | None:
        return _parse_float(value)


class _ModelsDevLimit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    context: int | None = None
    output: int | None = None

    @field_validator("context", "output", mode="before")
    @classmethod
    def _parse_limit_value(cls, value: object) -> int | None:
        return _parse_int(value)


class _ModelsDevModelRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    provider_model_id: str | None = None
    name: str | None = None
    tool_call: bool = False
    capabilities: tuple[str, ...] = ()
    cost: _ModelsDevCost = Field(default_factory=_ModelsDevCost)
    limit: _ModelsDevLimit = Field(default_factory=_ModelsDevLimit)
    release_date: str | None = None

    @field_validator("id", "provider_model_id", "name", "release_date", mode="before")
    @classmethod
    def _parse_optional_string(cls, value: object) -> str | None:
        return _parse_string(value)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _parse_capability_values(cls, value: object) -> tuple[str, ...]:
        return _parse_capabilities(value)


class _ModelsDevProviderPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    models: dict[str, object] = Field(default_factory=dict)


class _ModelsDevPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    anthropic: _ModelsDevProviderPayload | None = None
    openai: _ModelsDevProviderPayload | None = None
    google: _ModelsDevProviderPayload | None = None


class _CachedModelRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    name: str | None = None
    family: str | None = None
    provider: str | None = None
    harness: str | None = None
    cost_input: float | None = None
    cost_output: float | None = None
    context_limit: int | None = None
    output_limit: int | None = None
    capabilities: tuple[str, ...] = ()
    release_date: str | None = None

    @field_validator(
        "id",
        "name",
        "family",
        "provider",
        "harness",
        "release_date",
        mode="before",
    )
    @classmethod
    def _parse_optional_string(cls, value: object) -> str | None:
        return _parse_string(value)

    @field_validator("cost_input", "cost_output", mode="before")
    @classmethod
    def _parse_cost_value(cls, value: object) -> float | None:
        return _parse_float(value)

    @field_validator("context_limit", "output_limit", mode="before")
    @classmethod
    def _parse_limit_value(cls, value: object) -> int | None:
        return _parse_int(value)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _parse_capability_values(cls, value: object) -> tuple[str, ...]:
        return _parse_capabilities(value)


class _CachedModelsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fetched_at: float | None = None
    models: tuple[object, ...] = ()

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _parse_fetched_at(cls, value: object) -> float | None:
        return _parse_float(value)


def _default_cache_dir() -> Path:
    return resolve_cache_dir(resolve_repo_root())


def _resolve_cache_dir(cache_dir: Path | str | None) -> Path:
    if cache_dir is None:
        return _default_cache_dir()
    return Path(cache_dir)


def _cache_file(cache_dir: Path) -> Path:
    return cache_dir / _CACHE_FILE_NAME


def _infer_family(model_id: str) -> str:
    normalized = model_id.strip()
    if not normalized:
        return ""

    tail = normalized.rsplit("/", maxsplit=1)[-1]
    for separator in ("-", "."):
        if separator in tail:
            prefix = tail.split(separator, maxsplit=1)[0].strip()
            if prefix:
                return prefix
    return tail


def _capabilities(row: _ModelsDevModelRow) -> tuple[str, ...]:
    capabilities = set(row.capabilities)
    if row.tool_call:
        capabilities.add("tool_call")
    return tuple(sorted(capabilities))


def _parse_model_row(row: _ModelsDevModelRow, provider: str) -> DiscoveredModel | None:
    harness = _PROVIDER_TO_HARNESS.get(provider)
    if harness is None:
        return None

    capabilities = _capabilities(row)
    if "tool_call" not in capabilities:
        return None

    model_id = row.id or row.provider_model_id
    if model_id is None:
        return None

    name = row.name or model_id
    return DiscoveredModel(
        id=model_id,
        name=name,
        family=_infer_family(model_id),
        provider=provider,
        harness=harness,
        cost_input=row.cost.input,
        cost_output=row.cost.output,
        context_limit=row.limit.context,
        output_limit=row.limit.output,
        capabilities=capabilities,
        release_date=row.release_date,
    )


def _parse_models_payload(payload_obj: object) -> list[DiscoveredModel]:
    try:
        payload = _ModelsDevPayload.model_validate(payload_obj)
    except ValidationError:
        logger.warning("Unexpected models.dev payload shape; expected provider-keyed object")
        return []

    models: list[DiscoveredModel] = []
    for provider in _PROVIDER_TO_HARNESS:
        provider_payload = getattr(payload, provider)
        if provider_payload is None:
            continue

        for raw_row in provider_payload.models.values():
            try:
                row = _ModelsDevModelRow.model_validate(raw_row)
            except ValidationError:
                continue
            parsed = _parse_model_row(row, provider)
            if parsed is not None:
                models.append(parsed)

    return models


def fetch_models_dev() -> list[DiscoveredModel]:
    """Fetch and normalize coding-capable models from models.dev."""

    req = request.Request(
        _MODELS_DEV_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "meridian-channel/0.0.1",
        },
    )
    with request.urlopen(req, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        payload_obj = json.loads(response.read().decode("utf-8"))

    return _parse_models_payload(payload_obj)


def _deserialize_cached_model(row: _CachedModelRow) -> DiscoveredModel | None:
    if (
        row.id is None
        or row.name is None
        or row.family is None
        or row.provider is None
        or row.harness is None
    ):
        return None

    try:
        harness = HarnessId(row.harness)
    except ValueError:
        return None

    return DiscoveredModel(
        id=row.id,
        name=row.name,
        family=row.family,
        provider=row.provider,
        harness=harness,
        cost_input=row.cost_input,
        cost_output=row.cost_output,
        context_limit=row.context_limit,
        output_limit=row.output_limit,
        capabilities=tuple(sorted(row.capabilities)),
        release_date=row.release_date,
    )


def _read_cache(cache_file: Path) -> tuple[float, list[DiscoveredModel]] | None:
    if not cache_file.is_file():
        return None

    try:
        payload_obj = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to read models.dev cache at %s", cache_file, exc_info=False)
        logger.debug("Failed to read models.dev cache at %s", cache_file, exc_info=True)
        return None

    try:
        payload = _CachedModelsPayload.model_validate(payload_obj)
    except ValidationError:
        logger.warning("Ignoring invalid models.dev cache payload at %s", cache_file)
        return None

    if payload.fetched_at is None:
        logger.warning("Ignoring incomplete models.dev cache payload at %s", cache_file)
        return None

    models: list[DiscoveredModel] = []
    for raw_row in payload.models:
        try:
            row = _CachedModelRow.model_validate(raw_row)
        except ValidationError:
            continue
        parsed = _deserialize_cached_model(row)
        if parsed is not None:
            models.append(parsed)

    return payload.fetched_at, models


def _write_cache(cache_file: Path, models: list[DiscoveredModel]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {
        "fetched_at": int(time.time()),
        "models": [
            {
                **model.model_dump(),
                "harness": str(model.harness),
                "capabilities": list(model.capabilities),
            }
            for model in models
        ],
    }

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{cache_file.name}.",
        suffix=".tmp",
        dir=cache_file.parent,
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, cache_file)
    finally:
        tmp_path.unlink(missing_ok=True)


def refresh_models_cache(cache_dir: Path | str | None = None) -> list[DiscoveredModel]:
    """Force fetch from models.dev and update local cache.

    If remote fetch fails and no cache exists, returns an empty list.
    """

    resolved_dir = _resolve_cache_dir(cache_dir)
    cache_file = _cache_file(resolved_dir)
    cached = _read_cache(cache_file)

    try:
        models = fetch_models_dev()
        _write_cache(cache_file, models)
        return models
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        if cached is not None:
            logger.warning(
                "Failed to refresh models.dev cache at %s; using cached models",
                cache_file,
                exc_info=False,
            )
            logger.debug(
                "Failed to refresh models.dev cache at %s; using cached models",
                cache_file,
                exc_info=True,
            )
            return cached[1]

        logger.warning(
            "Failed to refresh models.dev catalog; no cached data available",
            exc_info=False,
        )
        logger.debug(
            "Failed to refresh models.dev cache at %s; no cached data available",
            cache_file,
            exc_info=True,
        )
        return []


def load_discovered_models(
    cache_dir: Path | str | None = None,
    *,
    force_refresh: bool = False,
) -> list[DiscoveredModel]:
    """Load discovered models from cache with 24-hour TTL."""

    resolved_dir = _resolve_cache_dir(cache_dir)
    if force_refresh:
        return refresh_models_cache(resolved_dir)

    cache_file = _cache_file(resolved_dir)
    cached = _read_cache(cache_file)
    if cached is not None:
        fetched_at, models = cached
        if time.time() - fetched_at < _CACHE_TTL_SECONDS:
            return models

    return refresh_models_cache(resolved_dir)


# ─── Aliases ───────────────────────────────────────────────────────────

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
        """Harness inferred from the model identifier via prefix routing."""

        if self.resolved_harness is not None:
            return self.resolved_harness
        return route_model(str(self.model_id)).harness_id

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


# ─── Catalog ───────────────────────────────────────────────────────────


def _catalog_path(repo_root: Path) -> Path:
    return resolve_state_paths(repo_root).models_path


def _coerce_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_optional_float(value: object, *, source: str) -> float | None:
    if value is None:
        return None
    parsed = _parse_float(value)
    if parsed is None:
        raise ValueError(f"Invalid value for '{source}': expected float.")
    return parsed


def _coerce_optional_int(value: object, *, source: str) -> int | None:
    if value is None:
        return None
    parsed = _parse_int(value)
    if parsed is None:
        raise ValueError(f"Invalid value for '{source}': expected int.")
    return parsed


def _coerce_bool(value: object, *, source: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Invalid value for '{source}': expected bool.")
    return value


def _coerce_model_visibility(raw_value: object) -> dict[str, object]:
    if raw_value is None:
        return {}
    if not isinstance(raw_value, dict):
        raise ValueError("Invalid value for 'model_visibility': expected table.")

    values: dict[str, object] = {}
    for key, value in cast("dict[str, object]", raw_value).items():
        if key in {"include", "exclude"}:
            values[key] = _coerce_pattern_list(value, source=f"model_visibility.{key}")
            continue
        if key == "max_input_cost":
            values[key] = _coerce_optional_float(value, source=f"model_visibility.{key}")
            continue
        if key == "max_age_days":
            values[key] = _coerce_optional_int(value, source=f"model_visibility.{key}")
            continue
        if key == "hide_date_variants":
            values[key] = _coerce_bool(value, source=f"model_visibility.{key}")
            continue
        logger.warning("Ignoring unknown models.toml key 'model_visibility.%s'.", key)
    return values


def load_model_visibility(repo_root: Path | None = None) -> ModelVisibilityConfig:
    if repo_root is None:
        return _DEFAULT_MODEL_VISIBILITY

    path = _catalog_path(resolve_repo_root(repo_root))
    if not path.is_file():
        return _DEFAULT_MODEL_VISIBILITY

    payload = _load_models_file_payload(path)
    updates = _coerce_model_visibility(payload.get("model_visibility"))
    if not updates:
        return _DEFAULT_MODEL_VISIBILITY
    return _DEFAULT_MODEL_VISIBILITY.model_copy(update=updates)


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, tuple | list):
        items = cast("tuple[object, ...] | list[object]", value)
        return "[" + ", ".join(_toml_literal(item) for item in items) + "]"
    raise ValueError(f"Unsupported models.toml value type: {type(value).__name__}")


def scaffold_models_toml() -> str:
    """Return commented defaults for `.meridian/models.toml`."""

    lines = [
        "# Model catalog overrides.",
        "# Uncomment and edit the sections below to customize aliases, routing, and visibility.",
        "",
        "# [aliases]",
        '# opus = "claude-opus-4-6"',
        '# gpt = "gpt-5.4"',
        "",
        "# [metadata.opus]",
        '# role = "default reviewer"',
        '# strengths = "deep review, architecture"',
        "",
        "# [harness_patterns]",
        f"# claude = {_toml_literal(_DEFAULT_HARNESS_PATTERNS[HarnessId.CLAUDE])}",
        f"# codex = {_toml_literal(_DEFAULT_HARNESS_PATTERNS[HarnessId.CODEX])}",
        f"# opencode = {_toml_literal(_DEFAULT_HARNESS_PATTERNS[HarnessId.OPENCODE])}",
        "",
        "# [model_visibility]",
        "# include = []",
        f"# exclude = {_toml_literal(_DEFAULT_MODEL_VISIBILITY.exclude)}",
        f"# hide_date_variants = {_toml_literal(_DEFAULT_MODEL_VISIBILITY.hide_date_variants)}",
        f"# max_age_days = {_toml_literal(_DEFAULT_MODEL_VISIBILITY.max_age_days)}",
        f"# max_input_cost = {_toml_literal(_DEFAULT_MODEL_VISIBILITY.max_input_cost)}",
        "",
    ]
    return "\n".join(lines)


def ensure_models_config(repo_root: Path) -> Path:
    """Scaffold `.meridian/models.toml` with commented defaults when missing."""

    path = _catalog_path(repo_root)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scaffold_models_toml(), encoding="utf-8")
    return path


def render_models_toml(payload: dict[str, object]) -> str:
    """Render normalized `.meridian/models.toml` content."""

    lines: list[str] = []
    aliases = payload.get("aliases")
    if isinstance(aliases, dict) and aliases:
        lines.append("[aliases]")
        for alias in sorted(cast("dict[str, object]", aliases)):
            value = cast("dict[str, object]", aliases)[alias]
            lines.append(f"{json.dumps(alias)} = {_toml_literal(value)}")

    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata:
        for alias in sorted(cast("dict[str, object]", metadata)):
            entry = cast("dict[str, object]", cast("dict[str, object]", metadata)[alias])
            if not entry:
                continue
            if lines:
                lines.append("")
            lines.append(f"[metadata.{json.dumps(alias)}]")
            for key in sorted(entry):
                lines.append(f"{key} = {_toml_literal(entry[key])}")

    harness_patterns = payload.get("harness_patterns")
    if isinstance(harness_patterns, dict) and harness_patterns:
        if lines:
            lines.append("")
        lines.append("[harness_patterns]")
        for harness in sorted(cast("dict[str, object]", harness_patterns)):
            lines.append(
                f"{harness} = {_toml_literal(cast('dict[str, object]', harness_patterns)[harness])}"
            )

    model_visibility = payload.get("model_visibility")
    if isinstance(model_visibility, dict) and model_visibility:
        if lines:
            lines.append("")
        lines.append("[model_visibility]")
        for key in sorted(cast("dict[str, object]", model_visibility)):
            value = cast("dict[str, object]", model_visibility)[key]
            lines.append(f"{key} = {_toml_literal(value)}")

    if not lines:
        return ""
    return "\n".join(lines) + "\n"


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


def _resolve_alias_harness(entry: AliasEntry, repo_root: Path | None) -> AliasEntry:
    resolved_harness = route_model(str(entry.model_id), repo_root=repo_root).harness_id
    return entry.model_copy(update={"resolved_harness": resolved_harness})


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


def _load_aliases_from_payload(payload: dict[str, object]) -> dict[str, AliasEntry]:
    metadata = _coerce_metadata_map(payload.get("metadata"))
    return _coerce_alias_entries(payload.get("aliases"), metadata=metadata)


def load_builtin_aliases() -> list[AliasEntry]:
    """Load built-in aliases bundled with meridian."""

    resource_path = Path(
        str(importlib.resources.files("meridian.resources") / _DEFAULT_ALIASES_RESOURCE)
    )
    entries = _load_aliases_from_payload(_load_models_file_payload(resource_path))
    return [entries[key] for key in sorted(entries)]


def load_user_aliases(repo_root: Path | None = None) -> list[AliasEntry]:
    """Load user-defined aliases from `.meridian/models.toml [aliases]`."""

    root = resolve_repo_root(repo_root)
    path = _catalog_path(root)
    if not path.is_file():
        return []

    entries = _load_aliases_from_payload(_load_models_file_payload(path))
    return [entries[key] for key in sorted(entries)]


def load_merged_aliases(repo_root: Path | None = None) -> list[AliasEntry]:
    """Load built-in aliases merged with user aliases (user wins by alias key)."""

    merged: dict[str, AliasEntry] = {entry.alias: entry for entry in load_builtin_aliases()}
    for entry in load_user_aliases(repo_root=repo_root):
        merged[entry.alias] = entry
    resolved_root = resolve_repo_root(repo_root) if repo_root is not None else None
    return [_resolve_alias_harness(merged[key], resolved_root) for key in sorted(merged)]


def resolve_alias(name: str, repo_root: Path | None = None) -> ModelId | None:
    """Resolve one alias to a model identifier."""

    normalized = name.strip()
    if not normalized:
        return None

    for entry in load_merged_aliases(repo_root=repo_root):
        if entry.alias == normalized:
            return entry.model_id
    return None


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
        _ = route_model(str(resolved.model_id), repo_root=repo_root)
        return resolved

    resolved_harness = route_model(normalized, repo_root=repo_root).harness_id
    return AliasEntry(
        alias="",
        model_id=ModelId(normalized),
        role=None,
        strengths=None,
        resolved_harness=resolved_harness,
    )
