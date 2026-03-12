# Consistency / Reduction Review

`MERIDIAN_WORK_DIR` was unset in this run, so this review was written to the fallback path `.meridian/work/review-consistency.md`.

## Findings

### HIGH: `spawn_store` can crash read paths on a malformed event, while `session_store` tolerates the same condition

- Files:
  - `src/meridian/lib/state/spawn_store.py:185-220`
  - `src/meridian/lib/state/session_store.py:102-140`
- Why it matters:
  - The state layer claims crash-only, self-healing behavior for truncated/corrupt state, but `spawn_store` only guards JSON decoding. A single schema-invalid `start`/`update`/`finalize` row can still raise during `model_validate()` and break `list_spawns()`, `get_spawn()`, `spawn show`, `spawn wait`, dashboards, and doctor flows.
  - `session_store` already solved this by catching `ValidationError` and dropping the bad row, so the two JSONL stores have diverged on the most important fault-tolerance rule.
- Before:

```python
# src/meridian/lib/state/spawn_store.py
def _parse_event(payload: dict[str, Any]) -> SpawnEvent | None:
    event_type = payload.get("event")
    if event_type == "start":
        return SpawnStartEvent.model_validate(payload)
    if event_type == "update":
        return SpawnUpdateEvent.model_validate(payload)
    if event_type == "finalize":
        return SpawnFinalizeEvent.model_validate(payload)
    return None
```

- After:

```python
from pydantic import ValidationError

def _parse_event(payload: dict[str, Any]) -> SpawnEvent | None:
    event_type = payload.get("event")
    try:
        if event_type == "start":
            return SpawnStartEvent.model_validate(payload)
        if event_type == "update":
            return SpawnUpdateEvent.model_validate(payload)
        if event_type == "finalize":
            return SpawnFinalizeEvent.model_validate(payload)
    except ValidationError:
        return None
    return None
```

- Reduction opportunity:
  - Extract the shared JSONL event-reader/lock/append helpers used by `spawn_store` and `session_store` into one utility so this kind of drift cannot recur.

### HIGH: MCP-exposed async operations are inconsistent; some offload blocking work, others block the event loop directly

- Files:
  - `src/meridian/lib/ops/spawn/api.py:118-124,187-193,247-253,276-282,304-310,422-428,572-578,641-647`
  - `src/meridian/lib/ops/diag.py:135-136`
  - `src/meridian/lib/ops/report.py:227-245`
  - `src/meridian/lib/ops/catalog.py:390-494`
- Why it matters:
  - `spawn.*` and `doctor` use `asyncio.to_thread(...)`, but `report.*` and all `catalog` async functions call sync implementations directly.
  - The manifest exposes `report.*`, `models.*`, `skills.*`, and `agents.list` on the MCP surface (`src/meridian/lib/ops/manifest.py:333-398,458-490`), so those handlers can block the server event loop on file IO, scanning, cache refresh, and config reads.
- Before:

```python
# src/meridian/lib/ops/report.py
async def report_create(
    payload: ReportCreateInput,
    ctx: RuntimeContext | None = None,
) -> ReportCreateOutput:
    return report_create_sync(payload, ctx=ctx)
```

- After:

```python
import asyncio

async def report_create(
    payload: ReportCreateInput,
    ctx: RuntimeContext | None = None,
) -> ReportCreateOutput:
    return await asyncio.to_thread(report_create_sync, payload, ctx=ctx)
```

- Reduction opportunity:
  - Either standardize on `asyncio.to_thread` for all sync-backed async wrappers, or make the manifest carry only sync handlers and generate the async wrapper in one place.

### MEDIUM: spawn statistics are implemented twice, and the two versions already diverge

- Files:
  - `src/meridian/lib/state/spawn_store.py:556-588`
  - `src/meridian/lib/ops/spawn/api.py:196-244`
- Why it matters:
  - `spawn_store.spawn_stats()` returns a generic `by_status`/`by_model` aggregation over derived records.
  - `spawn_stats_sync()` re-implements the aggregation with a different output shape and silently ignores statuses outside `succeeded`/`failed`/`cancelled`/`running` for dedicated counters.
  - The duplication means future schema/status changes have to be updated in two places, and one of them will drift.
- Simplification:
  - Keep one authoritative aggregation in the state layer, then shape CLI/MCP output from that result.

### MEDIUM: work-store error semantics are inconsistent inside the same module and leak into CLI error translation

- Files:
  - `src/meridian/lib/state/work_store.py:123-132,152-183,186-208`
  - `src/meridian/cli/main.py:663-669,821-824`
- Why it matters:
  - `get_work_item()` returns `None` for missing or invalid data.
  - `rename_work_item()` raises `ValueError` for missing items and collisions.
  - `update_work_item()` raises `KeyError` for missing items.
  - The CLI then has to special-case `KeyError` formatting to avoid Python repr noise.
- Consistency issue:
  - The same resource-not-found condition is represented three different ways.
- Simplification:
  - Pick one convention for store lookups and mutations, ideally `None` for pure getters and `ValueError` (or one project-specific exception) for command-side mutations.

### MEDIUM: runtime/root/chat resolution helpers are duplicated across ops modules and already disagree on defaults

- Files:
  - `src/meridian/lib/ops/work.py:16-25,68-73`
  - `src/meridian/lib/ops/report.py:17-20`
  - `src/meridian/lib/ops/spawn/api.py:58-66`
  - `src/meridian/lib/ops/spawn/execute.py:143-156,344-349`
  - `src/meridian/lib/ops/diag.py:56-57`
  - `src/meridian/lib/ops/runtime.py:27-37,70-72`
- Why it matters:
  - `_runtime_context`, `_state_root`, `_resolve_roots`, `_resolve_chat_id`, and `minutes_to_seconds` are all repeated.
  - The repeated helpers are not equivalent. Example: `work._resolve_chat_id()` returns an empty string when the context has no chat id, while `spawn.execute._resolve_chat_id()` invents `"c0"`.
- Simplification:
  - Move these into `ops.runtime` (or a small `ops.common`) and make missing-context policy explicit once.

### LOW: CLI registration is mostly copy-pasted boilerplate

- Files:
  - `src/meridian/cli/spawn.py:390-418`
  - `src/meridian/cli/work_cmd.py:153-183`
  - `src/meridian/cli/report_cmd.py:92-115`
  - `src/meridian/cli/agents_cmd.py:21-41`
  - `src/meridian/cli/models_cmd.py:33-55`
  - `src/meridian/cli/skills_cmd.py:33-55`
- Why it matters:
  - Each module repeats the same “scan manifest -> filter by group -> resolve handler -> set `__name__` -> register -> collect descriptions” loop.
  - The behavior is nearly identical, but error strings and default-command handling vary ad hoc.
- Simplification:
  - Extract a shared `register_manifest_cli_group(...)` helper that takes the app, group name, handler map, and optional default handler.

### LOW: there is dead or misleading API surface left behind

- Files:
  - `src/meridian/lib/ops/spawn/models.py:346-355`
  - `src/meridian/lib/ops/runtime.py:70-72`
  - `src/meridian/lib/state/reaper.py:498-500`
- Details:
  - `SpawnListFilters` is unused and still claims it is “converted into parameterized SQL”, which no longer matches the implementation.
  - `resolve_state_root()` in `ops.runtime` appears unused.
  - `reconcile_running_spawn()` is an unused compatibility alias over `reconcile_active_spawn()`.
- Simplification:
  - Remove them or keep them private with a clear deprecation comment if external callers still matter.

## Cross-file consistency notes

- `spawn_store.py` and `session_store.py` look like sibling JSONL stores, but they do not share a common parser/locking utility and have already drifted in validation behavior.
- `work_store.py` does not follow the same contract style as the event stores: it is directory-backed CRUD, mixes `None`/`ValueError`/`KeyError`, and does not share naming or serialization conventions with the JSONL stores.
- `paths.py` and `ops.runtime.py` overlap in responsibility for “resolve repo/state roots”, which is why `_state_root(...)` wrappers exist across multiple ops modules.
- `spawn/api.py` is the clearest sync/async pattern in the codebase; `report.py`, `catalog.py`, and `work.py` do not follow it consistently.
- Import style is mixed in state/ops consumers: several files import `meridian.lib.state` as a facade and also import leaf modules/constants directly in the same file, which makes the intended boundary unclear.
