"""Prompt composition helpers."""

from meridian.lib.prompt.assembly import (
    dedupe_skill_contents,
    dedupe_skill_names,
    load_skill_contents,
    resolve_run_defaults,
)
from meridian.lib.prompt.compose import (
    build_report_instruction,
    compose_run_prompt,
    compose_run_prompt_text,
    render_file_template,
)
from meridian.lib.prompt.reference import (
    ReferenceFile,
    TemplateVariableError,
    load_reference_files,
    parse_template_assignments,
    render_reference_blocks,
    resolve_template_variables,
    substitute_template_variables,
)
from meridian.lib.prompt.sanitize import sanitize_prior_output, strip_stale_report_paths

__all__ = [
    "ReferenceFile",
    "TemplateVariableError",
    "build_report_instruction",
    "compose_run_prompt",
    "compose_run_prompt_text",
    "dedupe_skill_contents",
    "dedupe_skill_names",
    "load_reference_files",
    "load_skill_contents",
    "parse_template_assignments",
    "render_file_template",
    "render_reference_blocks",
    "resolve_run_defaults",
    "resolve_template_variables",
    "sanitize_prior_output",
    "strip_stale_report_paths",
    "substitute_template_variables",
]
