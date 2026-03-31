# Phase 1d: Reference Resolver Dedup (R5)

## Scope

Extract a shared constructor from the three nearly-identical resolver branches in `reference.py`. Currently `_resolve_spawn_reference`, `_resolve_chat_reference`, and `_resolve_harness_session_reference` each repeat: normalize values, verify harness via `infer_harness_from_untracked_session_ref`, copy fields into `ResolvedSessionReference`. Phase 3 will add `source_execution_cwd` population to these branches -- doing that three times in duplicated code is error-prone.

After this phase, there's one shared builder that all three branches use.

## Files to Modify

### `src/meridian/lib/ops/reference.py`

#### 1. Extract a shared builder function

The three resolver functions share this pattern:
1. Get a harness_session_id from the source (spawn record, session record, or raw ref)
2. Normalize it
3. Look up the stored harness
4. Verify against `infer_harness_from_untracked_session_ref`
5. Build `ResolvedSessionReference` with the resolved values

Extract a helper that takes the common inputs and builds the result:

```python
def _build_tracked_reference(
    *,
    harness_session_id: str | None,
    stored_harness: str | None,
    source_chat_id: str | None,
    source_model: str | None,
    source_agent: str | None,
    source_skills: tuple[str, ...],
    source_work_id: str | None,
    repo_root: Path,
) -> ResolvedSessionReference:
    """Build a ResolvedSessionReference from tracked record fields.

    Shared by spawn, chat, and harness-session resolver paths.
    Handles harness normalization and verification.
    """
    normalized_session_id = _normalize_optional(harness_session_id)
    normalized_harness = _normalize_optional(stored_harness)
    registry = get_default_harness_registry()
    verified_harness = (
        infer_harness_from_untracked_session_ref(
            repo_root,
            normalized_session_id,
            registry=registry,
        )
        if normalized_session_id is not None
        else None
    )
    return ResolvedSessionReference(
        harness_session_id=normalized_session_id,
        harness=(
            str(verified_harness)
            if verified_harness is not None
            else normalized_harness
        ),
        source_chat_id=_normalize_optional(source_chat_id),
        source_model=_normalize_optional(source_model),
        source_agent=_normalize_optional(source_agent),
        source_skills=source_skills,
        source_work_id=_normalize_optional(source_work_id),
        tracked=True,
    )
```

#### 2. Simplify `_resolve_spawn_reference()`

```python
def _resolve_spawn_reference(
    state_root: Path, ref: str, repo_root: Path
) -> ResolvedSessionReference:
    row = spawn_store.get_spawn(state_root, ref)
    if row is None:
        return _resolve_untracked_reference(repo_root, ref)

    return _build_tracked_reference(
        harness_session_id=row.harness_session_id,
        stored_harness=row.harness,
        source_chat_id=row.chat_id,
        source_model=row.model,
        source_agent=row.agent,
        source_skills=row.skills,
        source_work_id=row.work_id,
        repo_root=repo_root,
    )
```

#### 3. Simplify `_resolve_chat_reference()`

```python
def _resolve_chat_reference(
    state_root: Path, ref: str, repo_root: Path
) -> ResolvedSessionReference:
    records = session_store.get_session_records(state_root, {ref})
    if not records:
        return _resolve_untracked_reference(repo_root, ref)

    session = records[0]
    return _build_tracked_reference(
        harness_session_id=_latest_harness_session_id(session),
        stored_harness=session.harness,
        source_chat_id=session.chat_id,
        source_model=session.model,
        source_agent=session.agent,
        source_skills=session.skills,
        source_work_id=session.active_work_id,
        repo_root=repo_root,
    )
```

#### 4. Simplify `_resolve_harness_session_reference()`

This one has a subtle difference: the `harness_session_id` falls back to `ref` if the stored value is empty. Preserve this:

```python
def _resolve_harness_session_reference(
    state_root: Path, ref: str, repo_root: Path
) -> ResolvedSessionReference:
    session = session_store.resolve_session_ref(state_root, ref)
    if session is None:
        return _resolve_untracked_reference(repo_root, ref)

    stored_harness_session_id = _normalize_optional(session.harness_session_id)
    effective_harness_session_id = stored_harness_session_id or ref

    return _build_tracked_reference(
        harness_session_id=effective_harness_session_id,
        stored_harness=session.harness,
        source_chat_id=session.chat_id,
        source_model=session.model,
        source_agent=session.agent,
        source_skills=session.skills,
        source_work_id=session.active_work_id,
        repo_root=repo_root,
    )
```

Note: for the harness-session path, the `harness_session_id` passed to `_build_tracked_reference` is the effective value (fallback applied BEFORE calling the builder). The builder's internal normalize won't further strip it since it's already normalized. The subtle fallback-to-ref behavior is preserved by the caller, not the builder.

## Dependencies

- **Requires**: Nothing.
- **Produces**: Clean resolver with one shared `_build_tracked_reference()` builder. Downstream phases extend it:
  - Phase 2b may expand the builder's parameter list for DTO consolidation.
  - Phase 3 adds `source_execution_cwd` parameter so all three resolver paths populate it in one place (instead of three).

## Patterns to Follow

- The builder is a private module function (`_build_tracked_reference`), consistent with the existing `_resolve_*` functions.
- The `_normalize_optional` helper is already used throughout -- the builder continues using it.

## Constraints

- **Behavior MUST NOT change.** The refactoring is purely structural. All three paths must produce identical output to the current code for any input.
- Pay special attention to the harness-session path's fallback: `stored_harness_session_id or ref`. This is the only difference between the three branches.
- The `_latest_harness_session_id` helper (used by `_resolve_chat_reference`) stays as-is -- it's chat-specific logic.
- `_resolve_untracked_reference` is unchanged -- it's already the shared fallback.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] `_build_tracked_reference()` exists and builds `ResolvedSessionReference` with harness verification
- [ ] All three `_resolve_*` functions use `_build_tracked_reference()`
- [ ] The harness-session path preserves the `stored_session_id or ref` fallback
- [ ] No behavioral changes -- identical outputs for identical inputs
