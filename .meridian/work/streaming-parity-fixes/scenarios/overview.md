# Scenarios — Master Index

Every edge case in `design/edge-cases.md` is represented here.

## Status Values

- **pending**
- **verified**
- **failed**
- **skipped**

## Index

| ID | Title | Tester | Status |
|---|---|---|---|
| S001 | Adapter omits `resolve_launch_spec` override | @unit-tester | pending |
| S002 | Base `ResolvedLaunchSpec` passed to Claude dispatch | @unit-tester | pending |
| S003 | Caller passes `None` as `PermissionResolver` | @verifier | pending |
| S004 | Resolver lacks `.config` | @unit-tester | pending |
| S005 | New Claude spec field forgotten in projection | @unit-tester | pending |
| S006 | New SpawnParams field forgotten in factory accounting | @unit-tester | pending |
| S007 | Streaming Codex with `sandbox=read-only` | @smoke-tester | pending |
| S008 | Streaming Codex with `approval=auto` | @smoke-tester | pending |
| S009 | Streaming Codex with `approval=default` | @smoke-tester | pending |
| S010 | Streaming Codex confirm rejection emits event | @smoke-tester | pending |
| S011 | Streaming Claude dedupes parent `--allowedTools` | @smoke-tester | pending |
| S012 | Subprocess Claude dedupe parity | @smoke-tester | pending |
| S013 | REST POST missing permission metadata behavior | @smoke-tester | pending |
| S014 | `run_streaming_spawn` with caller-supplied resolver | @smoke-tester | pending |
| S015 | Claude full-field round-trip | @unit-tester | pending |
| S016 | Codex permission matrix semantics | @unit-tester | pending |
| S017 | OpenCode model prefix normalization | @unit-tester | pending |
| S018 | OpenCode skills single-injection | @smoke-tester | pending |
| S019 | Codex `report_output_path` streaming behavior | @unit-tester | pending |
| S020 | `continue_fork=True` without session id | @unit-tester | pending |
| S021 | Claude subprocess/streaming arg-tail parity | @unit-tester | pending |
| S022 | User `--append-system-prompt` passthrough collision | @unit-tester | pending |
| S023 | `--allowedTools` merge from resolver + passthrough | @unit-tester | pending |
| S024 | `LaunchContext` parity across runners | @unit-tester | pending |
| S025 | Parent Claude permissions forwarded identically | @smoke-tester | pending |
| S026 | No duplicate runner constants | @verifier | pending |
| S027 | `python -O` preserves guard behavior | @verifier | pending |
| S028 | Harness binary missing from PATH | @smoke-tester | pending |
| S029 | Invalid codex app-server passthrough surfaced cleanly | @smoke-tester | pending |
| S030 | Projection completeness guard at import | @unit-tester | pending |
| S031 | No circular imports | @verifier | pending |
| S032 | Confirm-mode rejection event ordering | @unit-tester | pending |
| S033 | Streaming passthrough debug logs | @unit-tester | pending |
| S034 | `OpenCodeConnection` inherits `HarnessConnection` | @verifier | pending |
| S035 | Unified connection interface conformance | @unit-tester | pending |
| S036 | Delegated field has no consumer | @unit-tester | pending |
| S037 | Reserved-flag stripping | @unit-tester + @smoke-tester | pending |
| S038 | Codex fail-closed capability mismatch | @smoke-tester | pending |
