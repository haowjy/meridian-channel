"""Canonical Meridian depth helper behavior."""

import pytest

from meridian.lib.core.depth import (
    child_meridian_depth,
    current_meridian_depth,
    has_valid_meridian_depth,
    is_nested_meridian_depth,
    is_nested_meridian_process,
    is_root_side_effect_process,
    max_depth_reached,
    parse_meridian_depth,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 0),
        ("", 0),
        ("0", 0),
        ("2", 2),
        (" 3 ", 3),
        ("-4", 0),
        ("nope", 0),
        ("1.5", 0),
    ],
)
def test_parse_meridian_depth_normalizes_env_values(
    raw: str | None,
    expected: int,
) -> None:
    assert parse_meridian_depth(raw) == expected


def test_current_meridian_depth_reads_mapping() -> None:
    assert current_meridian_depth({"MERIDIAN_DEPTH": "4"}) == 4


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, True),
        ("", True),
        ("0", True),
        ("2", True),
        ("-4", False),
        ("nope", False),
        ("1.5", False),
    ],
)
def test_has_valid_meridian_depth_reports_parseability(
    raw: str | None,
    expected: bool,
) -> None:
    env = {} if raw is None else {"MERIDIAN_DEPTH": raw}
    assert has_valid_meridian_depth(env) is expected


def test_nested_predicate_uses_zero_based_depth() -> None:
    assert not is_nested_meridian_depth(0)
    assert is_nested_meridian_depth(1)
    assert not is_nested_meridian_process({"MERIDIAN_DEPTH": "0"})
    assert is_nested_meridian_process({"MERIDIAN_DEPTH": "2"})


def test_root_side_effect_process_fails_closed_for_malformed_depth() -> None:
    assert is_root_side_effect_process({})
    assert is_root_side_effect_process({"MERIDIAN_DEPTH": "0"})
    assert not is_root_side_effect_process({"MERIDIAN_DEPTH": "1"})
    assert not is_root_side_effect_process({"MERIDIAN_DEPTH": "-1"})
    assert not is_root_side_effect_process({"MERIDIAN_DEPTH": "garbage"})
    assert not is_root_side_effect_process({"MERIDIAN_DEPTH": "1.5"})


def test_child_meridian_depth_increments_only_when_requested() -> None:
    assert child_meridian_depth(2) == 3
    assert child_meridian_depth(2, increment_depth=False) == 2
    assert child_meridian_depth(-1, increment_depth=False) == 0


def test_max_depth_reached_matches_spawn_ceiling_contract() -> None:
    assert not max_depth_reached(current_depth=2, max_depth=3)
    assert max_depth_reached(current_depth=3, max_depth=3)
    with pytest.raises(ValueError, match="max_depth must be >= 0"):
        max_depth_reached(current_depth=0, max_depth=-1)
