# Phase Prep 4: Unify Reference Resolution

## Scope

Root CLI and spawn CLI resolve session references via completely different code paths:
- Root `--continue` uses `_resolve_continue_target()` in `cli/main.py` — resolves harness session IDs, checks `resolve_session_ref()` and `infer_harness_from_untracked_session_ref()`
- Spawn `--continue` uses `_source_spawn_for_follow_up()` in `ops/spawn/api.py` — resolves only spawn IDs (pNNN), extracts harness_session_id from spawn record

`--fork` needs a shared resolver that handles session IDs (cNNN), spawn IDs (pNNN), and raw harness UUIDs. Extract a shared `resolve_session_reference()` module.

## Intent

After this phase, there's one authoritative resolver for "given a user reference string, find the harness session ID and source metadata." Both root `--continue` and spawn `--continue` use it, and fork will use it too.

## Files to Modify

- **`src/meridian/lib/ops/reference.py`** (NEW) — Create the shared resolver module with:
  - `ResolvedSessionReference` dataclass — holds harness_session_id, harness, source_chat_id, source metadata
  - `resolve_session_reference(repo_root, ref)` — handles cNNN, pNNN, and raw UUID resolution

- **`src/meridian/cli/main.py`** — Update `_resolve_continue_target()` to delegate to the shared resolver. Keep `_ResolvedContinueTarget` as a thin wrapper if needed, or replace with `ResolvedSessionReference`.

- **`src/meridian/lib/ops/spawn/api.py`** — Update `_source_spawn_for_follow_up()` to optionally use the shared resolver for session ID extraction. The spawn-specific prompt derivation stays in `api.py`.

## Dependencies

- **Requires**: Prep 3 (session model changes landed).
- **Produces**: `resolve_session_reference()` function that Fork 1 and Fork 2 will use.

## Interface Contract

```python
# src/meridian/lib/ops/reference.py

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ResolvedSessionReference:
    """Result of resolving a user-provided session/spawn reference."""
    harness_session_id: str | None       # The harness-native session ID
    harness: str | None                  # Which harness owns this session
    source_chat_id: str | None           # Meridian chat ID (for lineage, None for raw UUIDs)
    source_model: str | None             # Model from source (for inheritance)
    source_agent: str | None             # Agent from source
    source_skills: tuple[str, ...]       # Skills from source
    source_work_id: str | None           # Work ID from source
    tracked: bool                        # Whether this ref maps to a known meridian session/spawn
    warning: str | None = None           # Resolution warnings

def resolve_session_reference(
    repo_root: Path,
    ref: str,
) -> ResolvedSessionReference:
    """Resolve a session or spawn reference to a harness session ID + metadata.

    Accepts:
    - Session ID: c367 → look up in session store
    - Spawn ID: p42 → look up in spawn store
    - Raw harness UUID: fall back to harness inference

    Raises ValueError if the reference is empty or clearly invalid.
    """
```

### Resolution logic:

1. If ref matches `p\d+` → look up in spawn store, extract harness_session_id + metadata
2. If ref matches `c\d+` → look up in session store, extract latest harness_session_id + metadata
3. Otherwise → treat as raw harness UUID, use `infer_harness_from_untracked_session_ref()`, source_chat_id=None

### Edge cases (from design spec):

- Session with multiple `harness_session_ids` (resumed multiple times): use the latest
- Spawn with `None` harness session ID: set `harness_session_id=None`, let caller decide error message
- Raw harness UUID: `source_chat_id=None` (no lineage), `tracked=False`

## Patterns to Follow

- See `_resolve_continue_target()` in `cli/main.py` (lines 713-761) for the current root resolution pattern.
- See `_source_spawn_for_follow_up()` in `ops/spawn/api.py` for the spawn resolution pattern.
- Use `resolve_session_ref()` from `state/session_store.py` for session lookups.
- Use `infer_harness_from_untracked_session_ref()` from `harness/session_detection.py` for raw UUID resolution.

## Constraints

- Do NOT change the external behavior of `--continue` on either root or spawn. The resolver is a refactor, not a feature change.
- Keep `_source_spawn_for_follow_up()` for spawn-specific logic (prompt derivation, model inheritance) — it can call the shared resolver internally.
- The shared resolver must NOT import from `cli/` — it lives in `lib/ops/`.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `meridian --continue cNNN` still works (resolves through shared resolver)
- [ ] `meridian spawn --continue pNNN -p "test"` still works
- [ ] The shared resolver handles all three ref formats: cNNN, pNNN, raw UUID
