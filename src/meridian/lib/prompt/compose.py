"""Prompt composition pipeline."""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from string.templatelib import Template
from typing import Literal

from meridian.lib.domain import SkillContent
from meridian.lib.prompt.reference import (
    ReferenceFile,
    render_reference_blocks,
    resolve_template_variables,
    substitute_template_variables,
)
from meridian.lib.prompt.sanitize import sanitize_prior_output, strip_stale_report_paths


def build_report_instruction(report_path: str) -> str:
    """Build the report instruction appended to each composed run prompt."""

    normalized = report_path.strip()
    if not normalized:
        raise ValueError("Report path must not be empty.")
    return (
        "# Report\n\n"
        "**IMPORTANT - Your final message should be a report of your work.**\n\n"
        "Include: what was done, key decisions made, files created/modified, "
        "verification results, and any issues or blockers.\n\n"
        "Use plain markdown. Meridian captures your final message as the run report."
    )


def _render_skill_blocks(skills: Sequence[SkillContent]) -> tuple[str, ...]:
    blocks: list[str] = []
    for skill in skills:
        content = skill.content.strip()
        if not content:
            continue
        blocks.append(f"# Skill: {skill.name}\n\n{content}")
    return tuple(blocks)


def _join_sections(sections: Sequence[str]) -> str:
    non_empty = [section.strip() for section in sections if section.strip()]
    return "\n\n".join(non_empty)


def _render_template(template: Template) -> str:
    """Render a PEP 750 template into plain text."""

    parts: list[str] = []
    for index, segment in enumerate(template.strings):
        parts.append(segment)
        if index < len(template.interpolations):
            parts.append(str(template.interpolations[index].value))
    return "".join(parts)


def compose_run_prompt(
    *,
    skills: Sequence[SkillContent],
    references: Sequence[ReferenceFile],
    user_prompt: str,
    report_path: str,
    agent_body: str = "",
    model_guidance: str = "",
    template_variables: Mapping[str, str | Path] | None = None,
    prior_output: str | None = None,
) -> Template:
    """Compose a run prompt with deterministic ordering and sanitization.

    Prompt assembly order:
    1) Skill content
    2) Agent profile body
    3) Model guidance
    4) Reference files
    5) Template variable substitution
    6) Report path instruction
    7) User prompt
    """

    skill_sections = _render_skill_blocks(skills)
    non_skill_sections: list[str] = []

    agent_body_text = agent_body.strip()
    if agent_body_text:
        non_skill_sections.append(f"# Agent Profile\n\n{agent_body_text}")

    model_guidance_text = model_guidance.strip()
    if model_guidance_text:
        non_skill_sections.append(f"# Model Guidance\n\n{model_guidance_text}")

    non_skill_sections.extend(render_reference_blocks(references))

    if prior_output is not None and prior_output.strip():
        non_skill_sections.append(sanitize_prior_output(prior_output))

    resolved_variables = resolve_template_variables(template_variables or {})
    rendered_non_skill_text = substitute_template_variables(
        _join_sections(non_skill_sections),
        resolved_variables,
    )
    sections_text = _join_sections((*skill_sections, rendered_non_skill_text))
    cleaned_user_prompt = substitute_template_variables(
        strip_stale_report_paths(user_prompt),
        resolved_variables,
    )
    report_instruction = build_report_instruction(report_path)

    if sections_text:
        return t"""{sections_text}

{report_instruction}

{cleaned_user_prompt}
"""
    return t"""{report_instruction}

{cleaned_user_prompt}
"""


def compose_run_prompt_text(
    *,
    skills: Sequence[SkillContent],
    references: Sequence[ReferenceFile],
    user_prompt: str,
    report_path: str,
    agent_body: str = "",
    model_guidance: str = "",
    template_variables: Mapping[str, str | Path] | None = None,
    prior_output: str | None = None,
) -> str:
    """Compose and render prompt text."""

    template = compose_run_prompt(
        skills=skills,
        references=references,
        user_prompt=user_prompt,
        report_path=report_path,
        agent_body=agent_body,
        model_guidance=model_guidance,
        template_variables=template_variables,
        prior_output=prior_output,
    )
    return _render_template(template).strip()


def render_file_template(
    template_path: Path,
    variables: Mapping[str, object],
    *,
    engine: Literal["t-string", "jinja2"] = "t-string",
) -> str:
    """Render template file with stdlib substitution or optional Jinja2 fallback."""

    content = template_path.read_text(encoding="utf-8")
    if engine == "jinja2":
        try:
            jinja2_module = importlib.import_module("jinja2")
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "Jinja2 fallback requested but jinja2 is not installed. "
                "Install with `meridian-channel[templates]`."
            ) from exc

        environment_cls = jinja2_module.Environment
        strict_undefined = jinja2_module.StrictUndefined
        env = environment_cls(
            autoescape=False,
            keep_trailing_newline=True,
            undefined=strict_undefined,
        )
        template = env.from_string(content)
        return str(template.render(**dict(variables)))

    normalized = {key: str(value) for key, value in variables.items()}
    return substitute_template_variables(content, normalized)
