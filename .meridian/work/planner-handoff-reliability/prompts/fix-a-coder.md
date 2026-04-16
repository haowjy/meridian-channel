# Task

Implement uniform, fail-loud prompt-size validation across the Claude, Codex, and OpenCode harness connection adapters in `meridian-cli`. The current state is that only the Codex adapter has a prompt-size limit, it's hardcoded at 50 KiB, and it silently truncates over-limit prompts before sending them to the harness. That has caused real planner handoffs to fail silently when prompt bundles grew past 50 KiB.

The full motivation and evidence is in `.meridian/work/planner-handoff-reliability/requirements.md` — read that first.

## Concrete changes

### 1. `src/meridian/lib/harness/connections/base.py`

Add near the top of the file (after imports):

- A module-level constant `MAX_INITIAL_PROMPT_BYTES: Final[int] = 10 * 1024 * 1024` with a brief comment naming the intent (uniform cap across adapters; fail-loud on overflow).
- A new exception class `PromptTooLargeError(RuntimeError)` with a constructor that takes `(actual_bytes: int, max_bytes: int, harness: str)` and produces a clear message along the lines of `"<harness>: initial prompt is N bytes, exceeds limit of M bytes"`.
- A module-level helper function `validate_prompt_size(config: ConnectionConfig) -> None` that encodes `config.prompt` as UTF-8, checks its byte length against `MAX_INITIAL_PROMPT_BYTES`, and raises `PromptTooLargeError` if over. The `harness` field in the error should come from `config.harness_id.value` (or equivalent — inspect the `HarnessId` type; `.value` is the convention used elsewhere in the adapter code).
- Add `PromptTooLargeError`, `MAX_INITIAL_PROMPT_BYTES`, and `validate_prompt_size` to `__all__`.

Keep `Final` imported from `typing` if not already.

### 2. `src/meridian/lib/harness/connections/codex_ws.py`

- Delete the local `_MAX_INITIAL_PROMPT_BYTES = 50 * 1024` constant (line 48).
- Delete the `_truncate_utf8` function (lines 775-779 or wherever it is).
- In the `start()` method, replace the silent-truncation block (currently around lines 273-286) with a single call to `validate_prompt_size(config)` at the top of the method, before any network I/O (before the `initialize` request, so a too-large prompt fails before any server interaction). The `initial_prompt` variable should then just be `config.prompt` directly.
- Remove the `warning/promptTruncated` event emission entirely. It's no longer meaningful because the spawn now fails loudly.
- Update the `turn/start` call to use `config.prompt` (or `initial_prompt` renamed cleanly) instead of the truncated version.
- Import `validate_prompt_size` from `meridian.lib.harness.connections.base`.

### 3. `src/meridian/lib/harness/connections/claude_ws.py`

- At the top of the `start()` method, add a call to `validate_prompt_size(config)` before any other work.
- Import `validate_prompt_size` from the base module.
- Leave `_STDOUT_READLINE_LIMIT` alone — it's a different kind of limit (inbound read buffer) and unrelated.

### 4. `src/meridian/lib/harness/connections/opencode_http.py`

- At the top of the `start()` method, add a call to `validate_prompt_size(config)` before any other work.
- Import `validate_prompt_size` from the base module.

## Testing

- Run `uv run pyright` — must be 0 errors.
- Run `uv run ruff check .` — must be clean.
- Run `uv run pytest-llm` — all existing unit tests must pass. If any test specifically exercises the old truncation behavior, update or remove it — we don't preserve the silent-truncation contract.

## Don't

- Don't change the limit to anything other than 10 MiB unless you have a specific reason and document it.
- Don't preserve the `warning/promptTruncated` event. It's gone.
- Don't add `opencode_http.py` its own limit constant — everything goes through `base.py`.
- Don't edit the impl-orchestrator profile or any agent profiles. That's out of scope for this work item.
- Don't commit. The orchestrator will handle staging and commit after verification + smoke lanes converge.

## Report

When done, report:
1. The exact files changed.
2. A short summary of what changed in each.
3. Output of `uv run pyright` and `uv run ruff check .`.
4. Any surprises or judgment calls made during implementation.
