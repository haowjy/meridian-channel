# Phase 6: Remove `--harness` CLI Flag from `meridian spawn`

## Scope

Remove the `--harness` parameter from the `meridian spawn` CLI command. Harness is set via subcommands (`meridian codex`), profile `harness:` field, or derived from model. Two ways to set the same thing is confusing.

Note: The `--harness` flag on the primary launch command (`meridian --harness`) is NOT removed — it's still the way to force harness for `meridian <prompt>` (non-subcommand) usage. Only the spawn subcommand flag goes away.

## Files to Modify

### `src/meridian/cli/spawn.py`

1. **Remove the `harness` parameter** from `_spawn_create()` function (lines 187-193):
   ```python
   # DELETE these lines:
   harness: Annotated[
       str | None,
       Parameter(
           name="--harness",
           help="Harness id to use. Overrides agent profile.",
       ),
   ] = None,
   ```

2. **Update `SpawnCreateInput` construction** in the normal (non-fork, non-continue) path (around line 330):
   ```python
   # Remove harness=harness from SpawnCreateInput(...)
   ```

3. **Update fork path** (around line 274): The fork path currently uses `harness` for cross-harness fork validation. After removal:
   - The `requested_harness` variable (line 232) needs to be removed or sourced differently
   - Cross-harness fork validation (`requested_harness != source_harness`) can be simplified — if no `--harness` flag exists, the validation checks whether the resolved harness (from profile/model) differs from the source harness. But this validation might move to `prepare.py` where the full resolution happens.
   - **Simplest approach**: Remove the pre-validation in the CLI and let `prepare.py` handle harness mismatch during fork resolution. The error message may be less specific but the behavior is correct.

4. **Update `SpawnCreateInput` harness field in fork path** (line 274):
   ```python
   # Was: harness=requested_harness or (resolved_reference.harness if not requested_model else None),
   # Now: harness=resolved_reference.harness if not requested_model else None,
   # Or simply: harness=None (let resolution handle it)
   ```

### `src/meridian/lib/ops/spawn/models.py`

Consider whether `SpawnCreateInput.harness` field should be removed entirely. It's still used by:
- `RuntimeOverrides.from_spawn_input()` which reads `payload.harness`
- Internal spawn APIs that might set harness programmatically

**Decision**: Keep `harness` on `SpawnCreateInput` — it's an internal model, not a CLI surface. The CLI just stops populating it from a flag. Internal callers (programmatic spawns) can still set it.

## Dependencies

- Requires Phase 4 (plan.py updated — no more `--harness` flowing through primary path)
- Requires Phase 5 (prepare.py updated — harness resolution uses layers, not explicit parameter)

## Interface Contract

- `meridian spawn --harness claude` → error (unknown flag)
- `meridian spawn -m sonnet` → derives harness from model (claude)
- `meridian spawn -a codex-agent` → uses profile harness
- `meridian codex -m sonnet` → subcommand harness (codex) + explicit model — unchanged
- Fork/continue paths work without `--harness` flag

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] `uv run meridian spawn --help` does NOT show `--harness`
- [ ] `uv run meridian spawn --harness claude -p test --dry-run` → error (unknown flag)
- [ ] `uv run meridian spawn -p test -m sonnet --dry-run` → works, derives claude harness
- [ ] `uv run meridian codex --dry-run` → works, codex harness via subcommand (unchanged)

## Agent Staffing

- 1 coder (default model)
- 2 reviewers: 1 on default model (correctness), 1 on a different model (backwards compat — verify no other code paths depend on spawn's --harness)
- 1 smoke-tester (verify CLI behavior)
- 1 verifier
