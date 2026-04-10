# S030: Projection completeness check runs at import

- **Source:** design/edge-cases.md E30 + p1411 finding H4 (D15 early detection)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Each projection module (`projections/claude.py`, `projections/codex.py`, `projections/opencode.py`) declares a module-level `_PROJECTED_FIELDS` frozenset and a module-level guard block that runs at import time.

## When
The projection module is first imported at application startup (which happens transitively via `lib/harness/adapter.py` at any meridian entrypoint).

## Then
- The guard compares `ClaudeLaunchSpec.model_fields` (minus `_SPEC_DELEGATED_FIELDS`) against `_PROJECTED_FIELDS`.
- If they match, import succeeds silently.
- If they drift, `ImportError` is raised with an actionable message: "Spec fields not projected: {missing_fields}. Add them to projections/claude.py::_PROJECTED_FIELDS and handle them in project_claude_spec_to_cli_args.".
- The error surfaces **at import time** (before any spawn runs), during meridian CLI startup.
- The guard runs regardless of `python -O`.

## Verification
- Unit test: directly `import meridian.lib.harness.projections.claude` in a pytest fresh-import fixture; verify normal import succeeds.
- Unit test: monkey-patch `ClaudeLaunchSpec.model_fields` via `type().__setattr__` or fixture to add a rogue field, then re-import using `importlib.reload`; assert `ImportError` with the expected message.
- Smoke test: introduce a deliberate drift in a local branch, run `uv run meridian --help`, observe the `ImportError` before any command runs.
- Repeat for `codex.py` and `opencode.py`.

## Result (filled by tester)
_pending_
