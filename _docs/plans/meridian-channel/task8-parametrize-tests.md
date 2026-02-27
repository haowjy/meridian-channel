# Task 8: Parametrize Duplicate Tests

**Status:** done

## Context

From the post-sandbox cleanup plan, Task 8 addresses test code duplication found by the dead code auditor.

---

## Task 8a: Parametrize clean-error tests

**File:** `tests/test_cli_ux_fixes.py`

Two nearly identical tests at lines ~142 and ~160 both verify that unknown-resource lookups emit clean errors (no tracebacks). They differ only in CLI args and expected error text.

**Reviewer feedback:** The `"error:"` assertion for skills-show is too generic for CI debugging. Use the specific error message instead.

**Before:** 2 functions, ~34 lines total

**After:** 1 parametrized function, ~20 lines:

```python
@pytest.mark.parametrize(
    "args,error_fragment",
    [
        (["skills", "show", "nonexistent-skill"], "Skill 'nonexistent-skill' not found"),
        (["run", "show", "nonexistent-run"], "Run 'nonexistent-run' not found"),
    ],
    ids=["skills-show", "run-show"],
)
def test_bug16_show_unknown_resource_emits_clean_error(
    args: list[str],
    error_fragment: str,
    package_root: Path,
    cli_env: dict[str, str],
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _seed_base_skills(repo_root)
    result = _run_cli(package_root=package_root, cli_env=cli_env, repo_root=repo_root, args=args)
    assert result.returncode != 0
    assert error_fragment in result.stderr
    assert "Traceback" not in result.stderr
```

**Note:** Verify the actual skills-show error message by checking the handler. If it doesn't emit `"Skill 'nonexistent-skill' not found"`, use whatever the actual message is. The key point is: use a specific fragment, not generic `"error:"`.

---

## Task 8b: Parametrize error classification tests

**File:** `tests/test_exec_errors_slice5a.py`

The file has 4 `classify_error` tests that follow the same pattern: `classify_error(1, msg)` → assert category. Two are UNRECOVERABLE, one RETRYABLE, one STRATEGY_CHANGE. Parametrize all 4 into one test.

**Reviewer feedback:** Add `import pytest` (currently absent). Parametrize the full classification matrix, not just the UNRECOVERABLE pair.

**Before:** 4 separate functions

**After:** 1 parametrized function covering all categories:

```python
import pytest

from meridian.lib.exec.errors import ErrorCategory, classify_error, should_retry


@pytest.mark.parametrize(
    "error_message,expected",
    [
        pytest.param(
            "Request failed: token limit exceeded for this model.",
            ErrorCategory.UNRECOVERABLE,
            id="token-limit",
        ),
        pytest.param(
            "Model not found: gpt-unknown",
            ErrorCategory.UNRECOVERABLE,
            id="model-not-found",
        ),
        pytest.param(
            "Network error: connection reset by peer",
            ErrorCategory.RETRYABLE,
            id="network-error",
        ),
        pytest.param(
            "Maximum context length exceeded; prompt too long.",
            ErrorCategory.STRATEGY_CHANGE,
            id="context-overflow",
        ),
    ],
)
def test_classify_error_categories(error_message: str, expected: ErrorCategory) -> None:
    assert classify_error(1, error_message) == expected
```

Keep `test_should_retry_honors_retryable_and_max_limit` as-is (tests a different function with multi-step assertions).

---

## Task 8c: Parametrize stale-report sanitization tests

**File:** `tests/test_prompt_slice3.py`

Two tests at lines ~92 and ~110 both call `strip_stale_report_paths(text)` and assert a stale instruction was removed while preserving the real prompt content. They differ in input text, removed fragment, and preserved fragment.

**Reviewer feedback:** LGTM. Add `-> None` return type hint to match existing test style.

**Before:** 2 functions, ~34 lines total

**After:** 1 parametrized function with extracted constants:

```python
_STALE_FILE_PATH_INSTRUCTION = """
# Report

**IMPORTANT - As your FINAL action**, write a report of your work to: `/tmp/old/report.md`

Include: what was done.

Use plain markdown. This file is read by the orchestrator to understand
what you did without parsing verbose logs.

Fix the bug in parser.py.
"""

_STALE_FINAL_MESSAGE_INSTRUCTION = """
# Report

**IMPORTANT - Your final message should be a report of your work.**

Include: what was done.

Use plain markdown. Meridian captures your final message as the run report.

Follow-up request for the same task.
"""


@pytest.mark.parametrize(
    "stale_text,should_remove,should_preserve",
    [
        pytest.param(
            _STALE_FILE_PATH_INSTRUCTION,
            "/tmp/old/report.md",
            "Fix the bug in parser.py.",
            id="file-path-instruction",
        ),
        pytest.param(
            _STALE_FINAL_MESSAGE_INSTRUCTION,
            "Your final message should be a report of your work.",
            "Follow-up request for the same task.",
            id="final-message-instruction",
        ),
    ],
)
def test_strip_stale_report_instructions(
    stale_text: str, should_remove: str, should_preserve: str
) -> None:
    cleaned = strip_stale_report_paths(stale_text)
    assert should_remove not in cleaned
    assert should_preserve in cleaned
```

---

## Verification

After implementation:
1. `uv run pytest tests/test_cli_ux_fixes.py tests/test_exec_errors_slice5a.py tests/test_prompt_slice3.py -v` — same number of test cases, all pass
2. `uv run pytest -x -q` — full suite passes
