# S018: OpenCode skills single-injection (no double-send)

- **Source:** design/edge-cases.md E18 + p1411 finding M4
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
OpenCode streaming spawn with `skills=("skill-a", "skill-b")` and `run_prompt_policy().include_skills = True` (the default). Real `opencode serve` is available on PATH.

## When
The adapter constructs the `OpenCodeLaunchSpec` and the streaming runner sends the HTTP session payload.

## Then
- Because `include_skills=True`, the prompt text inlines the skill content and the factory sets `spec.skills = ()`.
- The HTTP session payload does NOT separately carry skills.
- The remote `opencode serve` session receives each skill's content exactly once.
- Alternative path: if `include_skills=False`, the prompt does not inline, `spec.skills` is populated, and the HTTP payload carries them. Still exactly once.

## Verification
- Unit test: assert `spec.skills == ()` when `include_skills=True`.
- Unit test: assert `spec.skills == ("skill-a","skill-b")` when `include_skills=False`.
- Smoke test: run a real streaming OpenCode spawn, inspect the session on the `opencode serve` side (via its REST API), and confirm each skill's content appears exactly once in the session turns.
- Delta test: force the v1 "double-inject" path (return `spec.skills` populated AND inline them in the prompt) and confirm the smoke test fails.

## Result (filled by tester)
_pending_
