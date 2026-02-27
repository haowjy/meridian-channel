"""Reference-file loading and template substitution helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.workspace.session_files import (
    resolve_workspace_session_id,
    workspace_session_file_path,
)

_TEMPLATE_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class TemplateVariableError(ValueError):
    """Template substitution failed due to undefined or malformed variables."""


@dataclass(frozen=True, slots=True)
class ReferenceFile:
    """One reference file loaded from `-f` flags."""

    path: Path
    content: str


def parse_template_assignments(assignments: Sequence[str]) -> dict[str, str]:
    """Parse CLI template vars passed as `KEY=VALUE`."""

    parsed: dict[str, str] = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        normalized_key = key.strip()
        if not separator or not normalized_key:
            raise ValueError(
                "Invalid template variable assignment. Expected KEY=VALUE, "
                f"got '{assignment}'."
            )
        parsed[normalized_key] = value
    return parsed


def resolve_template_variables(
    variables: Mapping[str, str | Path],
    *,
    base_dir: Path | None = None,
) -> dict[str, str]:
    """Resolve template variable values (`@path`/Path -> file contents, else literal)."""

    root = (base_dir or Path.cwd()).resolve()
    resolved: dict[str, str] = {}
    for raw_key, raw_value in variables.items():
        key = raw_key.strip()
        if not key:
            raise ValueError("Template variable names must not be empty.")

        value: str | None = None
        path_candidate: Path | None = None
        if isinstance(raw_value, Path):
            path_candidate = raw_value
        else:
            candidate_text = raw_value
            if candidate_text.startswith("@"):
                path_candidate = Path(candidate_text[1:])
            else:
                value = candidate_text

        if path_candidate is not None:
            expanded = path_candidate.expanduser()
            resolved_path = (expanded if expanded.is_absolute() else root / expanded).resolve()
            if not resolved_path.is_file():
                raise FileNotFoundError(
                    f"Template variable '{key}' points to missing file: {resolved_path}"
                )
            value = resolved_path.read_text(encoding="utf-8")

        # `value` is guaranteed to be non-None by the branches above.
        assert value is not None
        resolved[key] = value
    return resolved


def substitute_template_variables(text: str, variables: Mapping[str, str]) -> str:
    """Substitute `{{KEY}}` placeholders; fail fast on undefined variables."""

    missing = sorted(
        {
            match.group(1)
            for match in _TEMPLATE_VAR_RE.finditer(text)
            if match.group(1) not in variables
        }
    )
    if missing:
        joined = ", ".join(missing)
        raise TemplateVariableError(f"Undefined template variables: {joined}")

    return _TEMPLATE_VAR_RE.sub(lambda match: variables[match.group(1)], text)


def load_reference_files(
    file_paths: Sequence[str | Path],
    *,
    base_dir: Path | None = None,
) -> tuple[ReferenceFile, ...]:
    """Load referenced files in input order."""

    root = (base_dir or Path.cwd()).resolve()
    loaded: list[ReferenceFile] = []
    for raw_path in file_paths:
        if isinstance(raw_path, str) and raw_path.startswith("@"):
            session_id = resolve_workspace_session_id()
            if session_id is None:
                raise ValueError(
                    "Session reference requires MERIDIAN_SESSION. "
                    "Set MERIDIAN_SESSION before using '-f @name'."
                )
            resolved = workspace_session_file_path(root, session_id, raw_path).resolve()
        else:
            path_obj = raw_path if isinstance(raw_path, Path) else Path(raw_path)
            expanded = path_obj.expanduser()
            resolved = (expanded if expanded.is_absolute() else root / expanded).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Reference file not found: {resolved}")
        loaded.append(ReferenceFile(path=resolved, content=resolved.read_text(encoding="utf-8")))
    return tuple(loaded)


def render_reference_blocks(references: Sequence[ReferenceFile]) -> tuple[str, ...]:
    """Render loaded references as isolated prompt sections."""

    blocks: list[str] = []
    for reference in references:
        body = reference.content.strip()
        if not body:
            continue
        blocks.append(f"# Reference: {reference.path}\n\n{body}")
    return tuple(blocks)
