# Windows CI and Platform-Conditioned Tests

## Goal

Add Windows to CI matrix and create platform-conditioned tests that verify the Windows branches in `lib/platform/` are exercised.

## Scope

### In Scope
1. **CI Matrix Expansion**: Add `windows-latest` to GitHub Actions workflow
2. **Platform Test Fixtures**: Add pytest markers/fixtures in `conftest.py` for platform-conditioned tests
3. **Platform Abstraction Tests**: Write tests for:
   - `lib/platform/locking.py` - verify Windows lock acquisition/release
   - `lib/platform/terminate.py` - verify Windows termination semantics (document the `terminate()` == `kill()` behavior)
4. **State Layer Tests**: Platform-aware tests for:
   - `lib/state/atomic.py` - verify `os.replace()` behavior, document Windows sharing violations

### Out of Scope
- Fixing the critical Windows issues identified in review (graceful shutdown, signal handlers)
- Full Windows feature parity
- ConPTY implementation

## Constraints

1. Tests must pass on both Windows and Linux
2. Use `pytest.mark.skipif` with `sys.platform` checks for platform-specific tests
3. Tests that only make sense on one platform should be clearly marked
4. Avoid tests that depend on Unix-specific signals (`SIGKILL`, `SIGTERM`)

## Success Criteria

1. CI runs on `windows-latest` in addition to `ubuntu-latest`
2. `uv run pytest` passes on both platforms
3. Platform module has test coverage that exercises Windows branches
4. Tests document known Windows limitations (e.g., `psutil.terminate() == kill()`)
