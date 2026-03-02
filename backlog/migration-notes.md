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

## 2026-03-02 Weirdness Log

### Checkpoint: dogfood preflight before Checkpoint 1
- Observed behavior: `meridian spawn` run `r1` returned a thin auto-extracted report that did not reflect substantive actions; `files_touched` also included non-file pseudo-paths (`scope/terminology`, `scope/problem/target`).
- Impact/risk: spawn report quality and `files_touched` reliability are not sufficient for checkpoint-level validation.
- Repro: `uv run meridian spawn --space s549 --background -m gpt-5.3-codex -p \"...checkpoint prompt...\"` then `uv run meridian --format json spawn wait --space s549 r1 --report --include-files`.
- Temporary handling: stop using dogfood runs for in-flight spawn/report semantics migration; validate via direct local edits + targeted pytest.
- Follow-up: investigate extraction pipeline + files-touched parsing (`src/meridian/lib/extract/report.py`, `src/meridian/lib/extract/files_touched.py`, streaming event normalization tests).

### Checkpoint: dogfood run cancellation before direct implementation
- Observed behavior: background spawn `r2` stayed running while awaiting result, creating workspace concurrency risk; required manual SIGINT on `_spawn_execute --spawn-id r2`.
- Impact/risk: concurrent repository writes can conflict with direct implementation and produce nondeterministic diffs.
- Repro: launch background spawn and inspect process list (`ps -eo pid,command | rg -- \"--spawn-id r2\"`), then interrupt (`kill -INT <pid>`).
- Temporary handling: terminate active dogfood spawn workers before manual implementation.
- Follow-up: consider adding `meridian spawn cancel <id>` and lock-aware safeguards for active local implementation sessions.

### Checkpoint: post-migration dogfood smoke (`p4`) noisy stderr/output
- Observed behavior: background spawn `p4` remained `running` until manually interrupted (`exit 130`), `output.jsonl` stayed empty, and `stderr.log` captured high-volume raw harness chatter.
- Noisy output patterns worth trimming (capture-side filtering backlog):
  - harness/session header block (`OpenAI Codex v...`, model/provider/sandbox/session metadata)
  - internal chain labels (`thinking`, `codex`, `exec`)
  - shell command echoes with workspace paths (`/bin/bash -lc ... in /home/...`)
  - per-command timing suffixes (`succeeded in 50ms`)
  - verbose MCP startup lines (`mcp: ... ready`)
- Impact/risk: token-heavy logs make spawn inspection noisy and expensive; signal-to-noise in failure triage is low when report extraction falls back to stderr.
- Repro:
  - `uv run meridian spawn create --space s549 --background -m gpt-5.3-codex -p "smoke: closed-space enforcement check" --timeout-secs 60`
  - inspect `.meridian/.spaces/s549/spawns/p4/stderr.log` and `.meridian/.spaces/s549/spawns/p4/output.jsonl`
- Temporary handling: preserve raw logs for debugging; summarize only actionable fields (`status`, `exit`, report presence, files touched) in human-facing output.
- Follow-up: add optional stderr sanitization/verbosity tiers and verify report extraction prefers structured output artifacts over raw harness stderr.

### Checkpoint: post-migration dogfood smoke (`p5`) empty-artifact failure
- Observed behavior: blocking spawn `p5` failed at timeout (`exit 3`) with both `stderr.log` and `output.jsonl` empty (`0` bytes), and no extracted report.
- Impact/risk: failure diagnostics are opaque; users cannot distinguish harness startup failure vs timeout vs wrapper error when artifacts are empty.
- Repro: `uv run meridian spawn create --space s549 -m claude-opus-4-6 -p "Smoke check..." --timeout-secs 45`.
- Temporary handling: create a manual report via `meridian report create --stdin --spawn p5` to preserve triage notes.
- Follow-up: ensure finalize path persists a minimal structured failure artifact (`error_code`, `failure_reason`, timeout marker) even when harness emits no stdout/stderr.

### Checkpoint: CLI UX observations (operator dogfood)
- Overall UX rating: mixed (`~6.5/10`) with strong command structure but weak failure/progress observability.
- What feels intuitive:
  - top-level command space is coherent (`space`, `spawn`, `report`, `models`, `skills`, `doctor`, `config`)
  - `spawn` + `report` split matches execution vs outcome mental model
  - spawn references (`@latest`, `@last-failed`, `@last-completed`) and env-based report resolution are useful
- What feels non-intuitive or inconsistent:
  - terminology drift (`run` wording still appears in some help/output while command surface is `spawn`)
  - space-state behavior is unclear from UX (closed vs active handling around spawn launch)
  - context/env strictness is inconsistent across commands (some infer, some require explicit scope)
- Operator pain points:
  - when a spawn hangs/fails, one-command diagnosis is weak; summaries often lack phase/failure reason
  - timeout/failed runs can produce empty artifacts, leaving exit code only
  - high-volume raw harness chatter buries actionable signal in stderr-heavy paths
- High-impact UX improvements:
  - add deterministic failure summary fields (`failure_reason`, timeout/cancel marker, last phase)
  - add running heartbeat/progress summaries for long spawns
  - keep raw logs, but split user-facing summary from debug verbosity
  - finish terminology cleanup (`run` -> `spawn`) across help/text
  - tighten and surface space-state rules at spawn entry
- Output that should be optional (`--debug`) rather than default:
  - harness/provider/session headers
  - internal chain markers (`thinking`, `codex`, `exec`)
  - echoed shell commands with absolute workspace paths
  - per-command timing chatter (`succeeded in XXms`)
  - verbose MCP startup noise
- Output that should remain default:
  - `spawn_id`, `status`, `duration`, `exit_code`
  - concise failure reason/cause
  - report/log artifact location(s)
