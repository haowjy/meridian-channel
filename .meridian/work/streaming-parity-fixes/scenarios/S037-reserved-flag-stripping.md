# S037: Reserved-flag stripping on passthrough args

- **Source:** design/permission-pipeline.md reserved-flags policy
- **Added by:** @design-orchestrator (revision pass 1)
- **Tester:** @unit-tester + @smoke-tester
- **Status:** pending

## Given
User includes reserved permission flags in passthrough args.

## When
Projection filtering runs.

## Then
- Reserved overrides are stripped (or merged for Claude allow/deny tools).
- Warning log emitted per stripped arg.
- Effective permission behavior remains resolver-driven.

## Verification
- Unit tests for Codex and Claude reserved sets.
- Smoke test verifies override attempt cannot escalate permissions.

## Result (filled by tester)
_pending_
