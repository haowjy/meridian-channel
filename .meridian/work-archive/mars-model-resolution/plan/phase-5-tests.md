# Phase 5: Tests — Update Existing + Add Coverage

## Scope

Update existing tests that reference removed functions. Add targeted tests for the new resolution flow and the model_id-vs-alias bug fix.

## Files to Modify

- `tests/lib/catalog/test_models.py` — update/remove tests for `route_model`, add tests for new `resolve_model` behavior

## What to Build

### Update existing tests

The existing tests reference `route_model()` which is removed:
- `test_route_model_uses_user_harness_patterns` (line ~46) — DELETE. User harness_patterns config is removed (Decision D3).
- `test_route_model_rejects_ambiguous_harness_patterns` (line ~60) — DELETE. Config-driven ambiguity no longer possible with hardcoded patterns.

### Add new tests

**Test: `resolve_model` returns concrete model_id for aliases (bug fix verification)**

This is the critical test for the live bug. When a user says `-m codex`, the returned `model_id` must be the concrete ID (e.g., `gpt-5.3-codex`), not `"codex"`.

```python
def test_resolve_model_returns_concrete_model_id(monkeypatch):
    """Verify resolve_model returns the concrete model_id, not the alias name."""
    # Mock _run_mars_models_resolve to return a known alias resolution
    def mock_mars_resolve(name, repo_root=None):
        if name == "codex":
            return {
                "name": "codex",
                "model_id": "gpt-5.3-codex",
                "harness": "codex",
                "harness_source": "auto_detected",
            }
        return None

    monkeypatch.setattr(
        "meridian.lib.catalog.model_aliases._run_mars_models_resolve",
        mock_mars_resolve,
    )
    result = resolve_model("codex")
    assert str(result.model_id) == "gpt-5.3-codex"
    assert result.alias == "codex"
    assert result.harness == HarnessId.CODEX
```

**Test: `resolve_model` pattern fallback for raw model IDs**

```python
def test_resolve_model_raw_model_id_pattern_fallback(monkeypatch):
    """Raw model IDs that aren't aliases use pattern fallback."""
    def mock_mars_resolve(name, repo_root=None):
        return None  # Not a known alias

    monkeypatch.setattr(
        "meridian.lib.catalog.model_aliases._run_mars_models_resolve",
        mock_mars_resolve,
    )
    result = resolve_model("claude-opus-4-6")
    assert str(result.model_id) == "claude-opus-4-6"
    assert result.alias == ""
    assert result.harness == HarnessId.CLAUDE
```

**Test: `resolve_model` raises for unknown model**

```python
def test_resolve_model_unknown_raises(monkeypatch):
    def mock_mars_resolve(name, repo_root=None):
        return None

    monkeypatch.setattr(
        "meridian.lib.catalog.model_aliases._run_mars_models_resolve",
        mock_mars_resolve,
    )
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_model("some-unknown-model")
```

**Test: `resolve_model` raises on unavailable harness**

```python
def test_resolve_model_unavailable_harness_raises(monkeypatch):
    def mock_mars_resolve(name, repo_root=None):
        return {
            "name": "opus",
            "model_id": "claude-opus-4-6",
            "harness": None,
            "harness_source": "unavailable",
            "harness_candidates": ["claude", "opencode"],
        }

    monkeypatch.setattr(
        "meridian.lib.catalog.model_aliases._run_mars_models_resolve",
        mock_mars_resolve,
    )
    with pytest.raises(ValueError, match="No installed harness"):
        resolve_model("opus")
```

**Test: `pattern_fallback_harness` basic routing**

```python
def test_pattern_fallback_harness():
    from meridian.lib.catalog.model_policy import pattern_fallback_harness

    assert pattern_fallback_harness("claude-opus-4-6") == HarnessId.CLAUDE
    assert pattern_fallback_harness("gpt-5.3-codex") == HarnessId.CODEX
    assert pattern_fallback_harness("gemini-pro") == HarnessId.OPENCODE

    with pytest.raises(ValueError):
        pattern_fallback_harness("totally-unknown-model")
```

## Dependencies

- Requires: Phase 3 and Phase 4 complete (all callers updated, dead code removed)

## Constraints

- Mock `_run_mars_models_resolve` in tests — don't depend on a real mars binary in unit tests
- Keep tests focused — don't test mars CLI behavior, only meridian's handling of mars output
- Use `monkeypatch` for mocking (pytest standard, already used in this codebase)

## Verification Criteria

- [ ] `uv run pytest-llm` passes — all new tests pass, no old tests broken
- [ ] `uv run pyright` passes
- [ ] `uv run ruff check .` passes
- [ ] The model_id-vs-alias bug is covered by an explicit test assertion
