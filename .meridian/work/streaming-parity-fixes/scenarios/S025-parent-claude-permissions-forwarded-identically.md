# S025: Parent Claude permissions forwarded identically

- **Source:** design/edge-cases.md E25 + p1411 findings M6 + H2
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
`CLAUDECODE=1` in the parent environment. Parent `.claude/settings.json` with a non-trivial permission block (e.g., `allowedTools=["Read","Edit"]`, `deniedTools=["Bash"]`). Spawn uses `ExplicitToolsResolver(allowed=("Read","Write"), denied=("Edit",))`.

## When
Both the subprocess runner and the streaming runner process the same plan.

## Then
- `read_parent_claude_permissions` produces the same parsed result for both runners.
- The preflight merge (via `merge_allowed_tools_flag`) folds parent allowances into `extra_args` identically.
- Both runners pass an identical `ClaudeLaunchSpec` downstream to the shared projection.
- The final launched command has the same `--allowedTools` (deduped) and same `--disallowedTools` value.
- The child env has the same `CLAUDECODE=1` and the same scrubbed variables.

## Verification
- Smoke test: launch the same spawn through both runners with the described inputs, capture the launched command via process introspection, assert equality of the arg tail and the env diff.
- Unit test: stub subprocess launch, assert `LaunchContext.env` and the projection output match byte-for-byte between the two paths.
- Delta test: modify parent settings mid-test and confirm both runners pick up the change identically on the next launch.

## Result (filled by tester)
_pending_
