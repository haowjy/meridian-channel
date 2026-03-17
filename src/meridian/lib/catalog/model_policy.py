"""Routing and visibility policy for the model catalog."""

from __future__ import annotations

import fnmatch
from datetime import date, timedelta
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from meridian.lib.core.types import HarnessId

SpawnMode = Literal["harness", "direct"]


class RoutingDecision(BaseModel):
    """Routing result for a model selection request."""

    model_config = ConfigDict(frozen=True)

    harness_id: HarnessId
    warning: str | None = None


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


DEFAULT_HARNESS_PATTERNS: dict[HarnessId, tuple[str, ...]] = {
    HarnessId.CLAUDE: ("claude-*", "opus*", "sonnet*", "haiku*"),
    HarnessId.CODEX: ("gpt-*", "o1*", "o3*", "o4*", "codex*"),
    HarnessId.OPENCODE: ("opencode-*", "gemini*", "*/*"),
}

DEFAULT_MODEL_VISIBILITY = ModelVisibilityConfig()


def match_pattern(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value, pattern)


def coerce_pattern_list(raw_value: object, *, source: str) -> tuple[str, ...]:
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


def coerce_harness_patterns(raw_section: object) -> dict[HarnessId, tuple[str, ...]]:
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
        patterns_by_harness[harness] = coerce_pattern_list(
            raw_patterns, source=f"harness_patterns.{harness_name}"
        )
    return patterns_by_harness


def coerce_model_visibility(raw_section: object) -> dict[str, object]:
    if raw_section is None:
        return {}
    if not isinstance(raw_section, dict):
        raise ValueError("Invalid value for 'model_visibility': expected table.")

    values: dict[str, object] = {}
    for key, value in cast("dict[str, object]", raw_section).items():
        if key in {"include", "exclude"}:
            values[key] = coerce_pattern_list(value, source=f"model_visibility.{key}")
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
        raise ValueError(f"Invalid value for 'model_visibility.{key}': unsupported key.")
    return values


def merge_harness_patterns(
    user_patterns: dict[HarnessId, tuple[str, ...]] | None = None,
) -> dict[HarnessId, tuple[str, ...]]:
    patterns = dict(DEFAULT_HARNESS_PATTERNS)
    if user_patterns:
        patterns.update(user_patterns)
    return patterns


def merge_model_visibility(overrides: dict[str, object] | None = None) -> ModelVisibilityConfig:
    if not overrides:
        return DEFAULT_MODEL_VISIBILITY
    return DEFAULT_MODEL_VISIBILITY.model_copy(update=overrides)


def route_model_with_patterns(
    model: str,
    *,
    patterns_by_harness: dict[HarnessId, tuple[str, ...]],
    mode: SpawnMode = "harness",
) -> RoutingDecision:
    normalized = model.strip()
    if mode == "direct":
        return RoutingDecision(harness_id=HarnessId.DIRECT)

    matched_harnesses = [
        harness
        for harness, patterns in patterns_by_harness.items()
        if any(match_pattern(pattern, normalized) for pattern in patterns)
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


def is_default_visible_model(
    *,
    model_id: str,
    aliased: bool,
    release_date: str | None,
    cost_input: float | None,
    all_model_ids: set[str],
    visibility: ModelVisibilityConfig,
) -> bool:
    if aliased:
        return True

    if visibility.include and not any(
        match_pattern(pattern, model_id) for pattern in visibility.include
    ):
        return False
    if any(match_pattern(pattern, model_id) for pattern in visibility.exclude):
        return False

    variant_bases = _date_variant_bases(model_id)
    if visibility.hide_date_variants and variant_bases and any(
        base in all_model_ids for base in variant_bases
    ):
        return False

    cutoff = _visibility_recency_cutoff(visibility.max_age_days)
    if cutoff is not None and release_date and release_date < cutoff:
        return False

    return not (
        visibility.max_input_cost is not None
        and cost_input is not None
        and cost_input >= visibility.max_input_cost
    )


_DATE_SUFFIX_PATTERNS = (
    r"^(?P<base>.+)-(?P<date>\d{8})$",
    r"^(?P<base>.+)-(?P<date>\d{4}-\d{2}-\d{2})$",
    r"^(?P<base>.+)-(?P<date>\d{2}-\d{2})$",
    r"^(?P<base>.+)-(?P<date>\d{2}-\d{4})$",
)


def _date_variant_bases(model_id: str) -> tuple[str, ...]:
    import re

    for pattern in _DATE_SUFFIX_PATTERNS:
        match = re.match(pattern, model_id)
        if match is None:
            continue
        base = match.group("base")
        candidates: list[str] = [base, f"{base}-0"]
        if base.endswith("-preview"):
            candidates.append(base.removesuffix("-preview"))
        return tuple(candidates)
    return ()


def _visibility_recency_cutoff(max_age_days: int | None) -> str | None:
    if max_age_days is None:
        return None
    return (date.today() - timedelta(days=max_age_days)).isoformat()


def _coerce_optional_float(value: object, *, source: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Invalid value for '{source}': expected float.")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Invalid value for '{source}': expected float.") from exc
    raise ValueError(f"Invalid value for '{source}': expected float.")


def _coerce_optional_int(value: object, *, source: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid value for '{source}': expected int.")
    return value


def _coerce_bool(value: object, *, source: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Invalid value for '{source}': expected bool.")
    return value
