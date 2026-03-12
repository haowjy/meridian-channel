import asyncio
import re
from pathlib import Path
from types import ModuleType

import pytest

from meridian.lib.ops import catalog, config, report, work
from meridian.lib.ops.runtime import async_from_sync


@pytest.mark.asyncio
async def test_async_from_sync_wraps_sync_function_and_uses_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    async def fake_to_thread(func: object, /, *args: object, **kwargs: object) -> object:
        calls.append((func, args, kwargs))
        assert callable(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    def sync_fn(value: int) -> int:
        return value + 1

    wrapped = async_from_sync(sync_fn)

    assert asyncio.iscoroutinefunction(wrapped)
    assert await wrapped(2) == 3
    assert calls == [(sync_fn, (2,), {})]


@pytest.mark.asyncio
async def test_async_from_sync_return_value_passes_through() -> None:
    marker = object()

    def sync_fn() -> object:
        return marker

    wrapped = async_from_sync(sync_fn)

    assert await wrapped() is marker


@pytest.mark.asyncio
async def test_async_from_sync_arguments_pass_through() -> None:
    seen: dict[str, object] = {}

    def sync_fn(*args: object, **kwargs: object) -> str:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return "ok"

    wrapped = async_from_sync(sync_fn)

    assert await wrapped(1, "two", flag=True, count=3) == "ok"
    assert seen["args"] == (1, "two")
    assert seen["kwargs"] == {"flag": True, "count": 3}


@pytest.mark.asyncio
async def test_async_from_sync_exceptions_propagate() -> None:
    def sync_fn() -> None:
        raise ValueError("boom")

    wrapped = async_from_sync(sync_fn)

    with pytest.raises(ValueError, match="boom"):
        await wrapped()


def test_async_from_sync_preserves_metadata() -> None:
    def sync_fn() -> None:
        return None

    wrapped = async_from_sync(sync_fn)

    assert wrapped.__name__ == sync_fn.__name__
    assert wrapped.__module__ == sync_fn.__module__


def _assert_async_ops_wrapped_via_async_from_sync(
    module: ModuleType,
    expected_wrappers: dict[str, str],
) -> None:
    assert module.__file__ is not None
    source = Path(module.__file__).read_text(encoding="utf-8")

    for async_name, sync_name in expected_wrappers.items():
        assignment_pattern = rf"^{async_name}\s*=\s*async_from_sync\(\s*{sync_name}\s*\)\s*$"
        assert re.search(assignment_pattern, source, flags=re.MULTILINE), (
            f"Expected {async_name} to be assigned with async_from_sync({sync_name})"
        )
        assert f"async def {async_name}(" not in source

        async_fn = getattr(module, async_name)
        sync_fn = getattr(module, sync_name)
        assert asyncio.iscoroutinefunction(async_fn)
        assert getattr(async_fn, "__wrapped__", None) is sync_fn


def test_report_ops_are_async_from_sync_wrapped() -> None:
    _assert_async_ops_wrapped_via_async_from_sync(
        report,
        {
            "report_create": "report_create_sync",
            "report_show": "report_show_sync",
            "report_search": "report_search_sync",
        },
    )


def test_work_ops_are_async_from_sync_wrapped() -> None:
    _assert_async_ops_wrapped_via_async_from_sync(
        work,
        {
            "work_dashboard": "work_dashboard_sync",
            "work_start": "work_start_sync",
            "work_list": "work_list_sync",
            "work_show": "work_show_sync",
            "work_update": "work_update_sync",
            "work_done": "work_done_sync",
            "work_switch": "work_switch_sync",
            "work_rename": "work_rename_sync",
            "work_clear": "work_clear_sync",
        },
    )


def test_catalog_ops_are_async_from_sync_wrapped() -> None:
    _assert_async_ops_wrapped_via_async_from_sync(
        catalog,
        {
            "models_list": "models_list_sync",
            "models_show": "models_show_sync",
            "models_refresh": "models_refresh_sync",
            "skills_list": "skills_list_sync",
            "skills_search": "skills_search_sync",
            "skills_load": "skills_load_sync",
            "agents_list": "agents_list_sync",
        },
    )


def test_config_ops_are_async_from_sync_wrapped() -> None:
    _assert_async_ops_wrapped_via_async_from_sync(
        config,
        {
            "config_init": "config_init_sync",
            "config_show": "config_show_sync",
            "config_set": "config_set_sync",
            "config_get": "config_get_sync",
            "config_reset": "config_reset_sync",
        },
    )


def test_report_runtime_context_helper_removed() -> None:
    assert report.__file__ is not None
    source = Path(report.__file__).read_text(encoding="utf-8")

    assert "def _runtime_context(" not in source
