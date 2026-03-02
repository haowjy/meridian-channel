# Migration Notes Backlog

Date added: 2026-03-02
Source: consolidated from `plans/new-philosophy/implementation/backlog.md`

## 2026-03-02 Notes

- Pre-existing dirty worktree includes docs that are partially migrated to `spawn` while code paths still include legacy `run` naming.
- `_docs/cli-spec-agent.md` and `_docs/cli-spec-human.md` existed before this work; verify against current plan instead of regenerating.
- `doctor` orphan-repair behavior is intentionally skipped when `MERIDIAN_SPACE_ID` is set, which changes some test expectations.
- Mechanical `run` -> `spawn` replacement touched non-domain usages (`uv run`, `subprocess.run`) and required manual restoration.
- `uv run pyright` reports strict-type diagnostics not scoped to this migration slice; full pytest suite was green in that context.
- Manual spawn smoke runs reported `input_tokens=0` and `output_tokens=0` despite successful execution, indicating usage propagation gap.
- Large reference-file spawn failed before model invocation with `OSError: [Errno 7] Argument list too long`, indicating argv-size handling gap.
- Infrastructure failure persisted as `status=failed` with weakly normalized `failure_reason` context.
- Failure path emitted extremely large traceback output with rich locals, causing token-heavy diagnostics.
- After switching Codex prompt transport to stdin and rendering `--file` inputs as path-only references, large-file spawn succeeded; token usage still persisted as `input_tokens=0` and `output_tokens=0`.
