"""Unit coverage for pure model alias entry parsing helpers."""

from meridian.lib.catalog.model_aliases import (
    _mars_list_to_entries,
    _mars_merged_to_entries,
    entry,
)


def test_entry_preserves_alias_defaults() -> None:
    alias = entry(
        alias="gpt",
        model_id="gpt-5.4",
        default_effort="high",
        default_autocompact=25,
    )

    assert alias.alias == "gpt"
    assert alias.model_id == "gpt-5.4"
    assert alias.default_effort == "high"
    assert alias.default_autocompact == 25


def test_entry_excludes_alias_defaults_from_serialized_output() -> None:
    alias = entry(
        alias="gpt",
        model_id="gpt-5.5",
        default_effort="low",
        default_autocompact=30,
    )

    dumped = alias.model_dump()

    assert "default_effort" not in dumped
    assert "default_autocompact" not in dumped


def test_mars_list_to_entries_maps_resolved_aliases() -> None:
    raw = [
        {
            "name": "opus",
            "harness": "claude",
            "mode": "pinned",
            "resolved_model": "claude-opus-4-6",
            "description": "Strong orchestrator.",
        },
        {
            "name": "gpt",
            "harness": "codex",
            "mode": "auto-resolve",
            "resolved_model": "gpt-5.4",
            "default_effort": "high",
            "autocompact": 30,
        },
    ]

    entries = _mars_list_to_entries(raw)
    by_name = {entry.alias: entry for entry in entries}

    assert set(by_name) == {"opus", "gpt"}
    assert by_name["opus"].model_id == "claude-opus-4-6"
    assert by_name["gpt"].default_effort == "high"
    assert by_name["gpt"].default_autocompact == 30


def test_mars_list_to_entries_leaves_defaults_unset_when_missing() -> None:
    entries = _mars_list_to_entries(
        [
            {
                "name": "sonnet",
                "harness": "claude",
                "mode": "auto-resolve",
                "resolved_model": "claude-sonnet-4",
            },
        ]
    )

    assert len(entries) == 1
    assert entries[0].default_effort is None
    assert entries[0].default_autocompact is None


def test_mars_list_to_entries_skips_aliases_without_name_or_resolution() -> None:
    entries = _mars_list_to_entries(
        [
            {
                "name": "opus",
                "harness": "claude",
                "mode": "auto-resolve",
                "resolved_model": "",
            },
            {
                "harness": "claude",
                "resolved_model": "claude-opus-4-6",
            },
        ]
    )

    assert entries == []


def test_mars_merged_to_entries_maps_pinned_aliases() -> None:
    entries = _mars_merged_to_entries(
        {
            "opus": {
                "harness": "claude",
                "model": "claude-opus-4-6",
                "description": "Strong.",
            },
            "gpt": {
                "harness": "codex",
                "model": "gpt-5.4",
                "default_effort": "high",
                "autocompact": 25,
            },
        }
    )
    by_name = {entry.alias: entry for entry in entries}

    assert set(by_name) == {"opus", "gpt"}
    assert by_name["opus"].description == "Strong."
    assert by_name["gpt"].default_effort == "high"
    assert by_name["gpt"].default_autocompact == 25


def test_mars_merged_to_entries_leaves_defaults_unset_when_missing() -> None:
    entries = _mars_merged_to_entries(
        {
            "sonnet": {
                "harness": "claude",
                "model": "claude-sonnet-4",
            },
        }
    )

    assert len(entries) == 1
    assert entries[0].default_effort is None
    assert entries[0].default_autocompact is None


def test_mars_merged_to_entries_skips_auto_resolve_aliases_without_model_id() -> None:
    entries = _mars_merged_to_entries(
        {
            "opus": {
                "harness": "claude",
                "provider": "anthropic",
                "match": ["opus"],
                "description": "Strong.",
            },
        }
    )

    assert entries == []
