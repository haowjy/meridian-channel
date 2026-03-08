# Slice: Create lib/core/ package

## Goal
Create a new `src/meridian/lib/core/` package by moving root-level modules from `src/meridian/lib/` into it. Leave re-export shims at the old paths so existing imports continue to work.

## Files to Move

1. **`lib/types.py` → `lib/core/types.py`** — NewType identifiers (SpaceId, SpawnId, etc.)
2. **`lib/domain.py` → `lib/core/domain.py`** — Core frozen models (Spawn, TokenUsage, etc.)
3. **`lib/context.py` → `lib/core/context.py`** — RuntimeContext (MERIDIAN_* env vars)
4. **`lib/sink.py` → `lib/core/sink.py`** — OutputSink protocol
5. **`lib/logging.py` → `lib/core/logging.py`** — Structured logging config

## Additional Work

6. **Create `lib/core/util.py`** — merge contents of `lib/formatting.py` and `lib/serialization.py` into one file. Both are small utility modules.
7. **Move `lib/ops/codec.py` → `lib/core/codec.py`** — Input coercion utilities.

## Re-export Shims

For EACH moved module, the OLD file must become a re-export shim. Example pattern:

```python
"""Compatibility shim — real code lives in meridian.lib.core.types."""
from meridian.lib.core.types import *  # noqa: F401,F403
```

For `lib/formatting.py` and `lib/serialization.py`, the shims should re-export from `lib/core/util`:
```python
"""Compatibility shim — real code lives in meridian.lib.core.util."""
from meridian.lib.core.util import *  # noqa: F401,F403
```

For `lib/ops/codec.py`, the shim should re-export from `lib/core/codec`:
```python
"""Compatibility shim — real code lives in meridian.lib.core.codec."""
from meridian.lib.core.codec import *  # noqa: F401,F403
```

## Rules
- Create `lib/core/__init__.py` (can be empty or minimal)
- **Do NOT change any existing imports in other files** — the re-export shims handle compatibility
- Preserve ALL content, docstrings, comments in the moved files
- When merging formatting.py + serialization.py, keep all functions from both
- No behavior changes — pure structural move

## Verification
Run `uv run pytest-llm` and `uv run pyright` — both must pass.
