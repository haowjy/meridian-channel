# S045: `extra_args` is forwarded verbatim to every transport

- **Source:** design/edge-cases.md E48 + decisions.md H1/D1 (revision round 3)
- **Added by:** @design-orchestrator (revision round 3)
- **Replaces:** [S037](S037-reserved-flag-stripping.md)
- **Tester:** @unit-tester + @smoke-tester
- **Status:** pending

## Given
A spawn configured with `extra_args = ("-c", "sandbox_mode=yolo", "--dangerous-flag", "--allowedTools", "C,D")`.

## When
The spec is projected to each harness's wire format — Claude subprocess, Claude streaming, Codex subprocess, Codex streaming (app-server command), OpenCode subprocess, OpenCode streaming (serve command). A smoke test launches the real harness end-to-end.

## Then
- Every `extra_args` element appears in the final command line or payload exactly as it was supplied, in the original order, at the passthrough tail position.
- Meridian does NOT strip `-c sandbox_mode=yolo`, `--dangerous-flag`, or `--allowedTools C,D`.
- Meridian does NOT rewrite or collapse any entry.
- Meridian DOES emit a debug log listing the verbatim `extra_args` at the projection boundary, so the audit trail makes it obvious what reached the harness.
- For Claude: the user's `--allowedTools C,D` coexists with any resolver-derived `--allowedTools A,B`. Both flags appear.
- For Codex: the user's `-c sandbox_mode=yolo` coexists with the resolver-derived `-c sandbox_mode="read-only"` (or whatever the permission config yields). Both appear. Codex's own argument handling decides the effective value.
- The harness either accepts the passthrough (smoke result: expected) or rejects it at its own startup (smoke result: harness-side error surfaces cleanly via S029).

## Verification
- Unit tests per projection (six total) asserting `extra_args` appears in the output exactly as supplied.
- Caplog assertion that the verbatim-passthrough debug log fires in `project_codex_spec_to_appserver_command` and `project_opencode_spec_to_serve_command`.
- Smoke test: launch a real streaming Codex spawn with `extra_args=("-c","sandbox_mode=yolo")`, capture process arguments via debug.jsonl, assert the user flag is present.
- Delta test: search the entire `projections/` package for `strip_reserved_passthrough`, `_RESERVED_CODEX_ARGS`, `_RESERVED_CLAUDE_ARGS`, `_reserved_flags.py` — assert zero matches.

## Result (filled by tester)
_pending_
