"""Mermaid style check orchestration."""

from __future__ import annotations

from collections.abc import Callable

from meridian.lib.mermaid.scanner import DiagramTarget
from meridian.lib.mermaid.style.types import StyleCheckOptions, StyleWarning, WarningCategory
from meridian.lib.mermaid.validator import BlockResult

CheckFn = Callable[[DiagramTarget, str | None], list[StyleWarning]]

_PRE_PARSE: list[tuple[WarningCategory, CheckFn]] = []
_POST_PARSE: list[tuple[WarningCategory, CheckFn]] = []


def run_style_checks(
    targets: list[DiagramTarget],
    validation_results: list[BlockResult],
    options: StyleCheckOptions,
) -> tuple[list[StyleWarning], list[StyleWarning]]:
    """Run style checks on all targets.

    Returns (active_warnings, suppressed_warnings).

    Pre-parse checks run on ALL targets (valid and invalid).
    Post-parse checks run only on targets that passed syntax validation.
    Warnings are deduplicated against syntax errors for the same line.
    Skips categories in options.disabled_categories.
    """
    if not options.enabled:
        return [], []

    result_by_location = {(result.file, result.line): result for result in validation_results}
    syntax_error_lines = {
        (result.file, result.line) for result in validation_results if not result.valid
    }

    raw_warnings: list[StyleWarning] = []

    for target in targets:
        validation_result = result_by_location.get((target.rel, target.start_line))
        diagram_type = validation_result.diagram_type if validation_result else None

        for category, check in _PRE_PARSE:
            if _should_skip_category(category, diagram_type, options):
                continue
            raw_warnings.extend(check(target, diagram_type))

        if validation_result is None or not validation_result.valid:
            continue

        for category, check in _POST_PARSE:
            if _should_skip_category(category, diagram_type, options):
                continue
            raw_warnings.extend(check(target, diagram_type))

    active_warnings: list[StyleWarning] = []
    suppressed_warnings: list[StyleWarning] = []
    for warning in raw_warnings:
        if (warning.file, warning.line) in syntax_error_lines:
            continue
        if warning.suppressed:
            suppressed_warnings.append(warning)
        else:
            active_warnings.append(warning)

    return active_warnings, suppressed_warnings


def get_all_categories() -> list[WarningCategory]:
    """Return all registered Mermaid style warning categories."""
    return [category for category, _check in [*_PRE_PARSE, *_POST_PARSE]]


def _should_skip_category(
    category: WarningCategory,
    diagram_type: str | None,
    options: StyleCheckOptions,
) -> bool:
    """Return True when a category should not run for this target."""
    if category.id in options.disabled_categories:
        return True
    return category.diagram_types is not None and diagram_type not in category.diagram_types


__all__ = [
    "CheckFn",
    "get_all_categories",
    "run_style_checks",
]
