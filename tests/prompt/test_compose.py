"""Prompt assembly tests that guard against context and prompt injection."""

from pathlib import Path

from meridian.lib.core.domain import SkillContent
from meridian.lib.launch.prompt import compose_run_prompt_text
from meridian.lib.launch.reference import load_reference_files


def test_compose_prompt_keeps_context_isolated_and_sanitized(tmp_path: Path) -> None:
    safe_ref = tmp_path / "safe.md"
    hidden_ref = tmp_path / "hidden.md"
    safe_ref.write_text("Safe context {{CTX}}", encoding="utf-8")
    hidden_ref.write_text("INJECTION: should never leak", encoding="utf-8")

    loaded_refs = load_reference_files([safe_ref], include_content=False)
    skill = SkillContent(
        name="worker",
        description="",
        tags=(),
        content="Skill content",
        path=str(tmp_path / "worker.md"),
    )
    user_prompt = (
        "**IMPORTANT - As your FINAL action**, write a report of your work to: "
        "`/tmp/stale.md`\n\nImplement the change with {{CTX}}."
    )

    composed = compose_run_prompt_text(
        skills=[skill],
        references=loaded_refs,
        user_prompt=user_prompt,
        template_variables={"CTX": "context"},
    )

    assert "INJECTION: should never leak" not in composed
    assert composed.count("As your final action, create the run report with Meridian.") == 1
    assert "/tmp/stale.md" not in composed
    assert str(safe_ref) in composed
    assert "Read these files from disk when gathering context:" in composed
    assert "Safe context {{CTX}}" not in composed
    assert "Implement the change with context." in composed


def test_compose_prompt_treats_reference_files_as_paths_only(tmp_path: Path) -> None:
    reference_file = tmp_path / "source.ts"
    reference_file.write_text("const template = '{{NOT_A_PROMPT_VAR}}';", encoding="utf-8")
    second_reference_file = tmp_path / "second.ts"
    second_reference_file.write_text("console.log('second');", encoding="utf-8")
    loaded_refs = load_reference_files([reference_file, second_reference_file], include_content=False)

    composed = compose_run_prompt_text(
        skills=[],
        references=loaded_refs,
        user_prompt="Inspect {{CTX}}.",
        template_variables={"CTX": "context"},
    )

    assert "{{NOT_A_PROMPT_VAR}}" not in composed
    assert "Inspect context." in composed
    assert str(reference_file) in composed
    assert str(second_reference_file) in composed
    assert composed.index(str(reference_file)) < composed.index(str(second_reference_file))
