from __future__ import annotations

from pathlib import Path

from meridian.lib.hooks.config import HooksConfig
from meridian.lib.hooks.registry import HookRegistry
from meridian.lib.hooks.types import Hook


def test_registry_orders_hooks_by_source_then_priority(tmp_path: Path) -> None:
    hooks = HooksConfig(
        hooks=(
            Hook(
                name="local-low",
                event="spawn.finalized",
                source="local",
                command="./local-low.sh",
                priority=0,
            ),
            Hook(
                name="project-mid",
                event="spawn.finalized",
                source="project",
                command="./project-mid.sh",
                priority=1,
            ),
            Hook(
                name="user-high",
                event="spawn.finalized",
                source="user",
                command="./user-high.sh",
                priority=10,
            ),
            Hook(
                name="user-low",
                event="spawn.finalized",
                source="user",
                command="./user-low.sh",
                priority=0,
            ),
            Hook(
                name="builtin-high",
                event="spawn.finalized",
                source="builtin",
                command="./builtin.sh",
                priority=99,
            ),
        )
    )
    registry = HookRegistry(Path(tmp_path), hooks_config=hooks)

    ordered = registry.get_hooks_for_event("spawn.finalized")

    assert [hook.name for hook in ordered] == [
        "builtin-high",
        "user-high",
        "user-low",
        "project-mid",
        "local-low",
    ]


def test_registry_excludes_disabled_hooks_from_event_lookup(tmp_path: Path) -> None:
    hooks = HooksConfig(
        hooks=(
            Hook(
                name="enabled-hook",
                event="work.done",
                source="project",
                command="./enabled.sh",
            ),
            Hook(
                name="disabled-hook",
                event="work.done",
                source="project",
                command="./disabled.sh",
                enabled=False,
            ),
        )
    )
    registry = HookRegistry(Path(tmp_path), hooks_config=hooks)

    assert [hook.name for hook in registry.get_hooks_for_event("work.done")] == ["enabled-hook"]
    assert [hook.name for hook in registry.get_all_hooks()] == ["enabled-hook", "disabled-hook"]
    assert registry.get_hook("disabled-hook") is not None


def test_registry_preserves_declaration_order_within_same_source_and_priority(
    tmp_path: Path,
) -> None:
    hooks = HooksConfig(
        hooks=(
            Hook(
                name="first",
                event="spawn.finalized",
                source="project",
                command="./first.sh",
                priority=5,
            ),
            Hook(
                name="second",
                event="spawn.finalized",
                source="project",
                command="./second.sh",
                priority=5,
            ),
            Hook(
                name="third",
                event="spawn.finalized",
                source="project",
                command="./third.sh",
                priority=5,
            ),
        )
    )
    registry = HookRegistry(Path(tmp_path), hooks_config=hooks)

    assert [hook.name for hook in registry.get_hooks_for_event("spawn.finalized")] == [
        "first",
        "second",
        "third",
    ]
