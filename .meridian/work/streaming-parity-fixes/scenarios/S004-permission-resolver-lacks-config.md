# S004: `PermissionResolver` implementation lacks `.config`

- **Source:** design/edge-cases.md E4 + p1411 finding H3 + L6
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
The `PermissionResolver` Protocol in v2 declares `config` as a required property returning a `PermissionConfig`. A developer adds a new resolver class but forgets to implement `config`.

## When
Pyright runs over the module containing the new resolver, and runtime code does `isinstance(resolver, PermissionResolver)`.

## Then
- Pyright reports that the class does not satisfy `PermissionResolver` because `config` is unimplemented.
- Runtime `isinstance(my_resolver, PermissionResolver)` returns `False` (because Protocol is `runtime_checkable`).
- Any call into `adapter.resolve_launch_spec(params, my_resolver)` is rejected by pyright.

## Verification
- Author a pytest fixture class `BrokenResolver` with only `resolve_flags` and no `config` property.
- Assert `isinstance(BrokenResolver(), PermissionResolver) is False`.
- Run `uv run pyright` against the fixture module and assert the "is not assignable to type PermissionResolver" diagnostic appears.
- Confirm the legacy `resolve_permission_config(perms)` getattr fallback helper is deleted from the tree.

## Result (filled by tester)
_pending_
