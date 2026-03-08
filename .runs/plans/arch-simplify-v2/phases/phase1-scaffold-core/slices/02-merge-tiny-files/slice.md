# Slice: Merge tiny files

## Goal
Merge several small utility files into their natural homes. Each merge absorbs a tiny file into a related module, reducing file count without changing behavior.

## Merges

### 1. Merge `state/id_gen.py` into `state/spawn_store.py`
- Read `src/meridian/lib/state/id_gen.py` (~70 lines) — ID generation utilities
- Read `src/meridian/lib/state/spawn_store.py` — spawn event store
- Move all content from `id_gen.py` into `spawn_store.py` (put the ID generation functions near the top, before the store class)
- Replace `id_gen.py` with a re-export shim: `from meridian.lib.state.spawn_store import *`
- Update any imports within `spawn_store.py` that referenced `id_gen`

### 2. Merge `harness/layout.py` into `harness/materialize.py`
- Read `src/meridian/lib/harness/layout.py` (~88 lines) — layout utilities
- Read `src/meridian/lib/harness/materialize.py` — materialization logic
- Move all content from `layout.py` into `materialize.py`
- Replace `layout.py` with a re-export shim: `from meridian.lib.harness.materialize import *`

### 3. Merge `harness/_common.py` + `harness/_strategies.py` into `harness/common.py`
- Read `src/meridian/lib/harness/_common.py` — common harness utilities
- Read `src/meridian/lib/harness/_strategies.py` — harness strategies
- Create a NEW file `src/meridian/lib/harness/common.py` with the merged content
- Replace `_common.py` with re-export shim: `from meridian.lib.harness.common import *`
- Replace `_strategies.py` with re-export shim: `from meridian.lib.harness.common import *`

### 4. Merge `extract/_io.py` into `extract/finalize.py`
- Read `src/meridian/lib/extract/_io.py` (~13 lines)
- Read `src/meridian/lib/extract/finalize.py`
- Move content from `_io.py` into `finalize.py`
- Replace `_io.py` with re-export shim: `from meridian.lib.extract.finalize import *`

### 5. Merge `exec/process_groups.py` into `exec/signals.py`
- Read `src/meridian/lib/exec/process_groups.py` (~29 lines)
- Read `src/meridian/lib/exec/signals.py`
- Move content from `process_groups.py` into `signals.py`
- Replace `process_groups.py` with re-export shim: `from meridian.lib.exec.signals import *`

## Rules
- Read each source file before modifying
- Keep all functions, classes, docstrings, comments
- When merging, resolve any import conflicts (duplicate imports, etc.)
- Replace absorbed files with re-export shims
- Do NOT update imports in files outside the merge targets — shims handle compatibility
- No behavior changes

## Verification
Run `uv run pytest-llm` and `uv run pyright` — both must pass.
