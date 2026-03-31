# Phase Fork 4: Codex Fork via File Copy

## Scope

Implement `fork_session()` on the Codex adapter. Codex's native `codex fork` command is interactive-only — no `codex exec fork`, no `--json`, no prompt argument. Instead, implement fork by copying the rollout JSONL file and inserting into the SQLite threads table. This is crash-safe following the project's atomic write pattern (tmp+rename).

## Intent

After this phase, the Codex adapter can fork sessions by file manipulation. The pipeline calls `fork_session()` before `build_command()` when the adapter requires it, and `build_command()` just sees a normal resume with the new session ID.

## Files to Modify

- **`src/meridian/lib/harness/codex.py`** — Major changes:
  1. Set `supports_session_fork = True` in capabilities
  2. Remove `FlagEffect.DROP` for `continue_fork` in strategy map
  3. Implement `fork_session(source_session_id: str) -> str` method

- **`src/meridian/lib/harness/adapter.py`** — Add `fork_session()` to `BaseSubprocessHarness` (or a mixin) as an optional override:
  ```python
  def fork_session(self, source_session_id: str) -> str:
      """Fork a harness session, return new session ID.
      Default raises NotImplementedError.
      Adapters where fork is a CLI flag (Claude, OpenCode) don't override.
      Adapters where fork requires file manipulation (Codex) override this.
      """
      raise NotImplementedError
  ```
  Add `has_fork_session` property or let callers check `capabilities.supports_session_fork` + `hasattr`.

## Dependencies

- **Requires**: Prep 5 (validation ensures source has a session ID).
- **Produces**: Codex fork capability. Fork 5 calls `fork_session()` in the pipeline when needed.

## Interface Contract

```python
# adapter.py (base)
class BaseSubprocessHarness:
    def fork_session(self, source_session_id: str) -> str:
        """Fork a harness session, return new session ID."""
        raise NotImplementedError

# codex.py
class CodexHarness(BaseSubprocessHarness):
    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            supports_session_fork=True,  # Changed from False
            # ... rest unchanged
        )

    def fork_session(self, source_session_id: str) -> str:
        """Copy rollout JSONL + SQLite row, return new session UUID."""
        # 1. Look up source in threads table
        # 2. Generate new UUID
        # 3. Stream-copy rollout file, rewriting session_meta.id on first line
        # 4. Atomic rename (tmp + os.replace)
        # 5. INSERT new threads row
        # 6. Return new UUID
```

### Codex storage layout (investigated):
```
~/.codex/state_5.sqlite          # SQLite DB with `threads` table
~/.codex/sessions/YYYY/MM/DD/    # Rollout JSONL files
  rollout-<timestamp>-<uuid>.jsonl
```

### Rollout JSONL structure:
- Line 0: `{"type": "session_meta", "payload": {"id": "<uuid>", ...}}`
- Rest: events with independent `turn_id` UUIDs — no session ID per-event

### Key implementation properties:
- **Crash-safe**: temp file + `os.replace()` follows project's `atomic_write_text` pattern
- **Memory-efficient**: stream line-by-line, not `f.read()` of entire file
- **SQLite insert after file durable**: orphaned file without threads row is harmless
- **`uuid4()`**: Codex tolerates non-v7 UUIDs for session identity
- **`timeout=10`**: on SQLite connect, handles contention with running Codex instances
- **`os.replace()` not `os.rename()`**: atomic across filesystems

### Pipeline integration (consumed by Fork 5):
- Call `fork_session()` BEFORE `build_command()` when `continue_fork=True` and adapter has `fork_session`
- Returned `new_id` replaces `continue_harness_session_id` in SpawnParams
- `build_command()` then sees a normal resume: `codex exec resume <new_id> "prompt"`
- **Skip** `fork_session()` when `dry_run=True` — don't mutate Codex state for previews

### Error handling:
```
Codex session 'UUID' not found in threads table.
Codex rollout file not found: /path/to/rollout.jsonl
Failed to fork Codex session: [SQLite/IO error details]
```

## Patterns to Follow

- See `atomic_write_text()` in `state/atomic.py` for the project's crash-safe write pattern.
- See existing `build_command()` in `codex.py` for how session IDs are used.
- Use `Path.home() / ".codex" / "state_5.sqlite"` for the DB path (match Codex's own resolution).

## Constraints

- Do NOT call `fork_session()` from this phase — that's Fork 5's job. This phase implements the method and enables the capability.
- Keep the SQLite interaction minimal — query one row, insert one row. No schema migrations.
- The `threads` table schema is Codex-internal. Document columns we touch and add a comment noting fragility.
- Do NOT attempt cleanup of orphaned fork files — track for future cleanup (MVP limitation).

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] Codex `capabilities.supports_session_fork` is now `True`
- [ ] Unit test: `fork_session()` with a mock SQLite DB copies rollout file correctly
- [ ] Unit test: first line of copied file has rewritten session_meta.id
- [ ] Unit test: crash during copy leaves no partial target file (atomic rename)
- [ ] Unit test: SQLite insert happens after file is durable
