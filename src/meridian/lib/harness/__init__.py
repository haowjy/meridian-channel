"""Harness package bootstrap."""

# pyright: reportPrivateUsage=false
# ruff: noqa: I001

from __future__ import annotations

_bootstrapped = False
_bootstrap_imports: tuple[object, ...] = ()


def _run_bootstrap() -> None:
    """Execute the load-bearing harness bootstrap sequence exactly once."""

    global _bootstrapped
    global _bootstrap_imports

    if _bootstrapped:
        return

    # Import order is load-bearing.
    #
    # 1) Adapter modules register HarnessBundle entries as module-load side effects.
    # 2) Projection modules execute import-time drift guards.
    # 3) Extractor modules bind runtime-checkable Protocol implementations.
    # 4) Cross-adapter SpawnParams accounting runs after all registrations.
    from meridian.lib.harness import claude as _claude
    from meridian.lib.harness import codex as _codex
    from meridian.lib.harness import opencode as _opencode

    from meridian.lib.harness.projections import project_claude as _project_claude
    from meridian.lib.harness.projections import (
        project_codex_streaming as _project_codex_streaming,
    )
    from meridian.lib.harness.projections import (
        project_codex_subprocess as _project_codex_subprocess,
    )
    from meridian.lib.harness.projections import (
        project_opencode_streaming as _project_opencode_streaming,
    )
    from meridian.lib.harness.projections import (
        project_opencode_subprocess as _project_opencode_subprocess,
    )

    from meridian.lib.harness.extractors import claude as _claude_extractor
    from meridian.lib.harness.extractors import codex as _codex_extractor
    from meridian.lib.harness.extractors import opencode as _opencode_extractor

    from meridian.lib.harness.launch_spec import _enforce_spawn_params_accounting

    _bootstrap_imports = (
        _claude,
        _codex,
        _opencode,
        _project_claude,
        _project_codex_subprocess,
        _project_codex_streaming,
        _project_opencode_subprocess,
        _project_opencode_streaming,
        _claude_extractor,
        _codex_extractor,
        _opencode_extractor,
    )
    _enforce_spawn_params_accounting()
    _bootstrapped = True


def ensure_bootstrap() -> None:
    """Ensure bundle/projection bootstrap has completed."""

    if _bootstrapped:
        return
    _run_bootstrap()


def _is_expected_partial_init(exc: ImportError) -> bool:
    message = str(exc)
    return (
        "partially initialized module 'meridian.lib.core.domain'" in message
        or "partially initialized module 'meridian.lib.core.types'" in message
    )


try:
    _run_bootstrap()
except ImportError as exc:
    if not _is_expected_partial_init(exc):
        raise
    import importlib

    for module_name in ("meridian.lib.core.types", "meridian.lib.core.domain"):
        try:
            importlib.import_module(module_name)
        except Exception:
            continue
    try:
        _run_bootstrap()
    except ImportError as retry_exc:
        if not _is_expected_partial_init(retry_exc):
            raise


__all__ = ["ensure_bootstrap"]
