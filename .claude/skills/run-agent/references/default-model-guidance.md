# Default Model Guidance

Use this default only when no custom files exist in `references/model-guidance/*.md`.

## Baseline picks

- Implementation: `gpt-5.3-codex`
- Review (medium/high risk): fan out across model families
- Fast/iterative UI loops: `claude-sonnet-4-6`
- Nuanced correctness/architecture: `claude-opus-4-6`
- Lightweight commit/message tasks: `claude-haiku-4-5`

## Practical rules

1. Prefer the smallest model choice that controls risk.
2. Use multiple reviewers only when risk justifies it.
3. Keep skill sets minimal and task-relevant.

## Real-world timings and observations (2026-02-27)

From a 4-cycle orchestrate session (~17 runs, ~2.5 hours):

| Model | Task type | Duration | Notes |
|---|---|---|---|
| `gpt-5.3-codex` | Implementation | 3–5 min | Reliable, good quality. Right default. |
| `gpt-5.3-codex` | Review (with focus areas) | 2–4 min | Thorough. Good for medium-risk review. |
| `claude-sonnet-4-6` | Focused review | 3–5 min | High-quality findings, well-structured. |
| `claude-opus-4-6` | Architecture / deep review | Slow — timed out at 15 min | Better as reviewer than implementer. Set `--timeout-secs 1800`. |
| `claude-haiku-4-5` | Commit messages | Not tested this session | Should test next session. |

**Key finding:** Multiple same-model reviewers with **different focus prompts** found more non-overlapping issues than a single cross-model review. **Prompt diversity > model diversity** for review fan-out.

**Opus caution:** Avoid using `claude-opus-4-6` as the implementer for broad tasks — it is thorough but slow enough to timeout on complex work. Use it as a deep reviewer with an extended timeout.
