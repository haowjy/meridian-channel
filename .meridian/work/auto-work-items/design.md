# Design: Auto Work Items

## Summary

Every session gets a work item automatically. When no work item is active at session start, meridian auto-creates one with a random three-word name (e.g., `brave-copper-fox`). This guarantees `$MERIDIAN_WORK_DIR` is always set, so agents always have a structured place for design docs, plans, and notes.

`work start` becomes smarter: if the current work item was auto-generated, rename it instead of creating a new one. Files already written to `$MERIDIAN_WORK_DIR` are preserved.

## Problem

Today, `$MERIDIAN_WORK_DIR` is only set when a spawn has an active work item. If no work item exists, the env var is unset. Agents have nowhere structured to put design docs, plans, and notes. They dump loose files into `.meridian/work/` or other random locations. This defeats the purpose of work item directories.

The fix is simple: always have a work item.

## 1. WorkItem Model Change

Add `auto_generated: bool` to `WorkItem`:

```python
class WorkItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    status: str
    created_at: str
    auto_generated: bool = False
```

`auto_generated` defaults to `False` for backward compatibility -- existing `work.json` files without the field parse correctly. Set to `True` only for auto-created items.

The `_serialize_work_item` function already uses `model_dump()`, so the new field serializes automatically.

## 2. Random Name Generation

Use the `coolname` library (already added as a dependency via `uv add coolname`). It provides curated word lists and slug generation with millions of combinations — no need to maintain our own word lists.

```python
# In work_store.py
from coolname import generate_slug

def generate_auto_name() -> str:
    """Return a random three-word slug for auto-generated work items."""
    return generate_slug(3)
```

`generate_slug(3)` returns names like `brave-copper-fox`, `calm-winter-song`. The library handles word diversity and avoids offensive combinations. Collisions are resolved by `_resolve_slug` appending `-2`, `-3`, etc.

## 3. Auto-Creation in `create_work_item`

Add a factory function for auto-generated items:

```python
def create_auto_work_item(state_root: Path) -> WorkItem:
    """Create an auto-generated work item with a random name."""
    work_dir = state_root / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    while True:
        name = generate_auto_name()
        slug = _resolve_slug(work_dir, name)
        item_dir = work_dir / slug
        try:
            item_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            continue

        item = WorkItem(
            name=slug,
            description="",
            status="open",
            created_at=_utc_now_iso(),
            auto_generated=True,
        )
        atomic_write_text(item_dir / "work.json", _serialize_work_item(item))
        return item
```

## 4. When Auto-Creation Triggers

At session start, inside `_session_execution_context` in `execute.py`. The work item must exist before any spawn launches so `$MERIDIAN_WORK_DIR` is set from the first spawn.

### 4a. Spawn execution path (`execute.py`)

In `_session_execution_context`, after `start_session()` returns a `chat_id`:

```python
@contextmanager
def _session_execution_context(...) -> Iterator[_SessionExecutionContext]:
    chat_id = start_session(state_root, ...)

    # Auto-create work item if session has none
    auto_work_id: str | None = None
    if state_root is not None:
        existing_work_id = session_store.get_session_active_work_id(state_root, chat_id)
        if not existing_work_id:
            auto_item = work_store.create_auto_work_item(state_root)
            session_store.update_session_work_id(state_root, chat_id, auto_item.name)
            auto_work_id = auto_item.name

    # ... rest of context manager
```

The auto-created `work_id` then flows through `_spawn_child_env` -> `RuntimeContext.to_env_overrides()` -> `$MERIDIAN_WORK_DIR`.

### 4b. Primary launch path

The primary launch in `process.py` / `command.py` follows the same pattern. When the primary session starts and has no active work item, auto-create one. This ensures the primary agent also has `$MERIDIAN_WORK_DIR` set.

### 4c. Skip when no state root

If `state_root` is `None` (no repo detected), skip auto-creation. Can't create work items without a `.meridian/` directory.

## 5. `work start` Rename-If-Auto

The key UX improvement: `work start "auth refactor"` renames an auto-generated item instead of creating a new one alongside it.

### Modified `work_start_sync`

```python
def work_start_sync(
    payload: WorkStartInput,
    ctx: RuntimeContext | None = None,
) -> WorkStartOutput:
    repo_root, state_root = _resolve_roots(payload.repo_root)
    chat_id = _resolve_chat_id(payload_chat_id=payload.chat_id, ctx=ctx)

    # Check if current work item is auto-generated
    current_work_id = session_store.get_session_active_work_id(state_root, chat_id)
    if current_work_id:
        current_item = work_store.get_work_item(state_root, current_work_id)
        if current_item is not None and current_item.auto_generated:
            # Rename auto-generated item to user's chosen name
            new_slug = work_store.slugify(payload.label)
            renamed = work_store.rename_work_item(state_root, current_work_id, new_slug)
            # Clear auto_generated flag
            cleared = work_store.update_work_item(
                state_root, renamed.name, auto_generated=False,
            )
            # Update spawn references
            for spawn in spawn_store.list_spawns(
                state_root, filters={"work_id": current_work_id}
            ):
                spawn_store.update_spawn(state_root, spawn.id, work_id=cleared.name)
            # Update session
            _set_active_work_id(state_root, chat_id=chat_id, work_id=cleared.name)
            _annotate_primary_spawn(state_root, chat_id=chat_id, work_id=cleared.name)
            return WorkStartOutput(
                name=cleared.name,
                status=cleared.status,
                description=cleared.description or payload.description.strip(),
                created_at=cleared.created_at,
                work_dir=_display_path(repo_root, state_root / "work" / cleared.name),
            )

    # Normal path: create new work item
    item = work_store.create_work_item(state_root, payload.label, payload.description.strip())
    _set_active_work_id(state_root, chat_id=chat_id, work_id=item.name)
    _annotate_primary_spawn(state_root, chat_id=chat_id, work_id=item.name)
    return WorkStartOutput(
        name=item.name,
        status=item.status,
        description=item.description,
        created_at=item.created_at,
        work_dir=_display_path(repo_root, state_root / "work" / item.name),
    )
```

The rename path reuses `work_store.rename_work_item` (moves directory, updates `work.json`). Spawn references are updated just like `work_rename_sync` does today.

### `update_work_item` gets `auto_generated` kwarg

```python
def update_work_item(
    state_root: Path,
    work_id: str,
    *,
    status: str | None = None,
    description: str | None = None,
    auto_generated: bool | None = None,
) -> WorkItem:
    current = get_work_item(state_root, work_id)
    if current is None:
        raise KeyError(work_id)

    updated = current.model_copy(
        update={
            "status": current.status if status is None else status,
            "description": current.description if description is None else description,
            "auto_generated": current.auto_generated if auto_generated is None else auto_generated,
        }
    )
    atomic_write_text(_work_item_path(state_root, work_id), _serialize_work_item(updated))
    return updated
```

## 6. `work rename` Clears Auto-Generated Flag

When `work_rename_sync` renames an auto-generated item, clear the flag. The user has explicitly named it.

```python
def work_rename_sync(payload: WorkRenameInput, ctx: ...) -> WorkRenameOutput:
    # ... existing rename logic ...
    item = work_store.rename_work_item(state_root, old_name, payload.new_name)

    # Clear auto_generated if it was set
    current = work_store.get_work_item(state_root, item.name)
    if current is not None and current.auto_generated:
        work_store.update_work_item(state_root, item.name, auto_generated=False)

    # ... rest of existing logic (update spawns, session) ...
```

## 7. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Multiple `work start` calls | First renames auto-generated item (clears flag). Second creates new item (current is no longer auto-generated). |
| `work switch` to auto-generated item | No special behavior. It's a valid work item. |
| `work rename` on auto-generated item | Renames and clears `auto_generated` flag. |
| `work clear` then `work start` | `work clear` unsets active. Next session start would auto-create again. `work start` after `clear` in the same session creates new (no auto-generated item to rename). |
| Session with no state root | Skip auto-creation entirely. |
| `work list` output | Auto-generated items show up like any other. Could optionally add a marker, but probably unnecessary. |
| Existing sessions (upgrade) | No migration needed. `auto_generated` defaults to `False`. Old items behave exactly as before. |

## 8. Skill Updates

### `meridian-work` SKILL.md

Add section:

```markdown
## Auto-generated work items

Every session starts with a work item. If you don't have one, meridian creates
one with a random name (e.g., `calm-brook-wren`). This ensures `$MERIDIAN_WORK_DIR`
is always available.

When you know what you're working on, name it:

    meridian work start "auth refactor"

This renames the auto-generated item -- all docs you've already written to
`$MERIDIAN_WORK_DIR` are preserved under the new name.

**Always use `$MERIDIAN_WORK_DIR` for design docs, plans, and notes.**
Never write loose files to `.meridian/work/`.
```

### `meridian-spawn-agent` SKILL.md

Add to the Work Items section:

```markdown
### Design Docs and Notes

Every session has a work item directory at `$MERIDIAN_WORK_DIR`. Use it for
design docs, plans, diagrams, and any coordination artifacts:

    echo "$MERIDIAN_WORK_DIR"
    # .meridian/work/auth-refactor/

Write docs there, not loose in `.meridian/work/` or the repo root.
```

## 9. Implementation Sequence

1. **Add `auto_generated` to `WorkItem`** -- model change, `update_work_item` kwarg. Tests pass (default `False`, backward compatible).
2. **Add word lists + `generate_auto_name` + `create_auto_work_item`** -- pure functions, unit-testable.
3. **Wire auto-creation into session start** -- `_session_execution_context` in `execute.py`, primary launch in `process.py`.
4. **Modify `work_start_sync`** -- rename-if-auto logic.
5. **Modify `work_rename_sync`** -- clear flag on rename.
6. **Update skills** -- `meridian-work` and `meridian-spawn-agent` SKILL.md changes.
7. **Tests** -- `uv run pytest-llm && uv run pyright`.

Steps 1-2 are safe, isolated changes. Step 3 is the core behavior change. Steps 4-5 are the UX polish. Step 6 is documentation.
