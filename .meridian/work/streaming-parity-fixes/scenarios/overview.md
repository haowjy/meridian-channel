# Scenarios — Master Index

Every edge case enumerated in `design/edge-cases.md` has a corresponding scenario file here. Testers execute these against the implementation; the work is not complete while any scenario is `pending` or `failed`.

## Status Values

- **pending** — scenario exists, no tester has executed it
- **verified** — tester executed it, confirmed expected behavior with evidence
- **failed** — tester executed it, observed wrong behavior (blocks phase completion)
- **skipped** — tester could not execute it; must document why and get orchestrator sign-off

## Index

| ID | Title | Tester | Status |
|---|---|---|---|
| S001 | Adapter omits `resolve_launch_spec` override | @unit-tester | pending |
| S002 | Caller passes base `ResolvedLaunchSpec` to `ClaudeConnection.start` | @unit-tester | pending |
| S003 | Caller passes `None` as `PermissionResolver` | @verifier | pending |
| S004 | `PermissionResolver` implementation lacks `.config` | @unit-tester | pending |
| S005 | New field on `ClaudeLaunchSpec`, projection forgets it | @unit-tester | pending |
| S006 | New field on `SpawnParams`, factory doesn't map it | @unit-tester | pending |
| S007 | Streaming Codex with `sandbox=read-only` | @smoke-tester | pending |
| S008 | Streaming Codex with `approval=auto` | @smoke-tester | pending |
| S009 | Streaming Codex with `approval=default` | @smoke-tester | pending |
| S010 | Streaming Codex with `approval=confirm` rejects and emits event | @smoke-tester | pending |
| S011 | Streaming Claude dedupes parent `--allowedTools` | @smoke-tester | pending |
| S012 | Subprocess Claude dedupes parent `--allowedTools` (parity) | @smoke-tester | pending |
| S013 | REST server POST with no permission block | @smoke-tester | pending |
| S014 | `run_streaming_spawn` with caller-supplied resolver | @smoke-tester | pending |
| S015 | Claude spec round-trip with every field populated | @unit-tester | pending |
| S016 | Codex spec round-trip with every permission combo | @unit-tester | pending |
| S017 | OpenCode spec with `opencode-` model prefix | @unit-tester | pending |
| S018 | OpenCode skills single-injection (no double-send) | @smoke-tester | pending |
| S019 | Codex `report_output_path` on streaming path | @unit-tester | pending |
| S020 | `continue_fork=True` with no `continue_session_id` | @unit-tester | pending |
| S021 | Claude subprocess vs streaming byte-equal arg tails | @unit-tester | pending |
| S022 | User passes `--append-system-prompt` in `extra_args` | @unit-tester | pending |
| S023 | `--allowedTools` merged from resolver + extra_args | @unit-tester | pending |
| S024 | `LaunchContext` parity across runners | @unit-tester | pending |
| S025 | Parent Claude permissions forwarded identically | @smoke-tester | pending |
| S026 | No duplicate constants across runners | @verifier | pending |
| S027 | `python -O` strips nothing meaningful | @verifier | pending |
| S028 | Harness binary missing from PATH | @smoke-tester | pending |
| S029 | `codex app-server` rejects passthrough args surfaces cleanly | @smoke-tester | pending |
| S030 | Projection completeness check runs at import | @unit-tester | pending |
| S031 | No circular imports | @verifier | pending |
| S032 | Codex approval rejection event visible on queue | @unit-tester | pending |
| S033 | Debug log for passthrough args on streaming | @unit-tester | pending |
| S034 | `OpenCodeConnection` inherits `HarnessConnection` | @verifier | pending |
| S035 | All three connections satisfy the same Protocol | @unit-tester | pending |

## Appending Rules

- **Design orchestrator** seeds during design from enumerated edge cases and audit reports.
- **Planner** appends during planning if new cross-phase or phase-boundary hazards surface.
- **Impl orchestrator** appends during implementation if a coder or tester discovers an edge case the design missed.
- **Testers** never append; they execute and fill the Result section.

Any new scenario must carry a tester assignment before it is considered part of the verification contract.
