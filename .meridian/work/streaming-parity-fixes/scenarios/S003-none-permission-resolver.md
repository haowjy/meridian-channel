# S003: Caller passes `None` as `PermissionResolver`

- **Source:** design/edge-cases.md E3 + p1411 finding H3 + L6
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier
- **Status:** pending

## Given
The codebase forbids `cast("PermissionResolver", None)` patterns. Every call site must pass a real resolver.

## When
A developer attempts to add `adapter.resolve_launch_spec(params, None)` or reintroduces the `cast("PermissionResolver", None)` pattern.

## Then
- Pyright rejects the call: `None` is not assignable to parameter `perms: PermissionResolver`.
- The two v1 sites (`streaming_runner.py:457` and `server.py:203`) no longer contain the cast — grep across the tree returns zero matches for `cast("PermissionResolver"` and zero matches for `cast('PermissionResolver'`.

## Verification
- `uv run pyright` against the full tree reports zero errors. Any attempt to reintroduce the cast pattern shows up in the diff.
- `uv run ruff check .` clean.
- Manual grep: `rg "cast\\(\\s*['\"]PermissionResolver['\"]"` over `src/` returns nothing.

## Result (filled by tester)
_pending_
