# Phase Prep 1: SessionMode Enum + SessionIntent

## Scope

Replace scattered booleans (`fresh`, `is_resume`, `continue_fork`) with a proper `SessionMode` enum and `SessionIntent` dataclass on the primary launch side. Today the launch pipeline uses `fresh: bool` on `LaunchRequest` and checks `bool(continue_harness_session_id)` in multiple places to infer resume vs fresh. Adding fork introduces a third mode — without this refactor, the interaction matrix becomes 8 boolean states.

The spawn side already has `SessionContinuation` with `continue_fork: bool` — this phase brings the primary launch side to equivalent clarity.

## Intent

After this phase, every decision point in the launch pipeline reads a single `SessionMode` enum value instead of doing boolean arithmetic. Fork (Phase Fork 5) will add `SessionMode.FORK` to this enum rather than threading yet another boolean.

## Files to Modify

- **`src/meridian/lib/launch/types.py`** — Define `SessionMode` enum (FRESH, RESUME, FORK), `SessionIntent` dataclass. Update `LaunchRequest` to carry `session_mode: SessionMode = SessionMode.FRESH` and `forked_from_chat_id: str | None = None`. Keep `fresh`, `continue_harness_session_id`, `continue_chat_id` fields temporarily for backward compat but mark as deprecated with comments. Update `build_primary_prompt()` to switch on `session_mode` instead of `request.fresh`.
- **`src/meridian/lib/launch/plan.py`** — Update `resolve_primary_launch_plan()` to use `request.session_mode` instead of `bool(explicit_harness_session_id)` for `is_resume` decisions. Both SpawnParams construction sites (MERIDIAN_HARNESS_COMMAND override path at line ~218 and normal path at line ~289) use the new mode.
- **`src/meridian/cli/main.py`** — Update `_run_primary_launch()` to set `session_mode=SessionMode.RESUME` when `continue_ref` is provided, `SessionMode.FRESH` otherwise. Stop setting `fresh=True/False` — derive it from session_mode if any downstream code still reads it.

## Dependencies

- **Requires**: Nothing — this is the first phase.
- **Produces**: `SessionMode` enum and `SessionIntent` dataclass that Fork 5 extends with `FORK` variant. Updated `LaunchRequest` model.

## Interface Contract

```python
from enum import Enum
from dataclasses import dataclass

class SessionMode(str, Enum):
    """How this session relates to prior conversation state."""
    FRESH = "fresh"       # New session, no prior context
    RESUME = "resume"     # Continue existing session in-place
    FORK = "fork"         # Branch from existing session (added in Fork 5)

@dataclass(frozen=True)
class SessionIntent:
    """Resolved session continuation intent for the launch pipeline."""
    mode: SessionMode
    harness_session_id: str | None = None  # Source session to resume/fork
    chat_id: str | None = None             # Meridian chat ID to reuse (resume only)
    forked_from_chat_id: str | None = None # Lineage tracking (fork only)
```

## Patterns to Follow

- Enum style: see `src/meridian/lib/core/types.py` for existing enum patterns (e.g., `HarnessId`).
- Pydantic model updates: frozen models, `ConfigDict(frozen=True)`.
- The enum should be a `str, Enum` so it serializes cleanly to JSON/YAML.

## Constraints

- Do NOT implement fork logic yet. `SessionMode.FORK` exists in the enum but no code path sets it. This phase is purely about replacing FRESH/RESUME booleans with the enum.
- Do NOT remove the `fresh` field from `LaunchRequest` yet — too many tests and downstream consumers. Add `session_mode` alongside it and make `fresh` derive from `session_mode` (or vice versa via a property).
- Do NOT touch spawn-side code (`ops/spawn/`). That has its own `SessionContinuation` model.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `uv run meridian --help` works
- [ ] `uv run meridian --dry-run` produces a fresh session plan with `SessionMode.FRESH`
- [ ] `build_primary_prompt()` returns continuation guidance when `session_mode=SessionMode.RESUME`
- [ ] `build_primary_prompt()` returns fresh session guidance when `session_mode=SessionMode.FRESH`
