# S026: No duplicate constants across runners

- **Source:** design/edge-cases.md E26 + p1411 finding M6
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier (+ @refactor-reviewer)
- **Status:** pending

## Given
The v2 design places shared runner constants in `src/meridian/lib/launch/constants.py`:
- `DEFAULT_*_SECONDS` (timeouts)
- `DEFAULT_INFRA_EXIT_CODE`
- `_BLOCKED_CHILD_ENV_VARS`
- `BASE_COMMAND` tuples per harness (the canonical subprocess base and streaming base)

## When
A grep-based audit runs across `src/meridian/lib/launch/runner.py`, `src/meridian/lib/launch/streaming_runner.py`, and all harness connection modules.

## Then
- Every constant listed above has exactly one definition site, in `launch/constants.py`.
- `runner.py` and `streaming_runner.py` import them — no local redefinition.
- `claude_ws.py`, `codex_ws.py`, `opencode_http.py` do not contain their own `BASE_COMMAND` tuples; they use the shared constants.
- No drift: if the subprocess base changes, the streaming base (and both projections) see the change automatically.

## Verification
- `rg "DEFAULT_INFRA_EXIT_CODE\\s*=" src/ -t py` returns exactly 1 match, in `constants.py`.
- Same for each listed constant.
- `rg "_BLOCKED_CHILD_ENV_VARS\\s*=" src/ -t py` → exactly 1 match.
- Refactor-reviewer audits the pair of runner files looking for module-level constant assignments that duplicate the shared set.
- Test: `from meridian.lib.launch.constants import BASE_COMMAND_CLAUDE_SUBPROCESS, BASE_COMMAND_CLAUDE_STREAMING` (or equivalent names) succeeds.

## Result (filled by tester)
_pending_
