"""Shared pytest fixtures."""

import os
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "posix_only: test requires POSIX semantics")
    config.addinivalue_line("markers", "windows_only: test requires Windows semantics")
    config.addinivalue_line("markers", "unit: pure logic tests, no IO")
    config.addinivalue_line("markers", "integration: one real boundary")
    config.addinivalue_line("markers", "e2e: full CLI invocation")
    config.addinivalue_line("markers", "contract: parity/drift checks")
    config.addinivalue_line("markers", "slow: takes >1s")


@pytest.fixture
def package_root() -> Path:
    return PACKAGE_ROOT


@pytest.fixture(autouse=True, scope="session")
def _isolate_meridian_home(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Set MERIDIAN_HOME for the full test session."""

    test_home = tmp_path_factory.mktemp("meridian-home")
    os.environ["MERIDIAN_HOME"] = str(test_home)


@pytest.fixture(autouse=True)
def _clean_meridian_runtime_env(
    monkeypatch: pytest.MonkeyPatch,
    _isolate_meridian_home: None,
) -> None:
    """Isolate tests from parent harness runtime state environment."""

    session_home = os.environ.get("MERIDIAN_HOME")
    for key in tuple(os.environ):
        if key.startswith("MERIDIAN_"):
            monkeypatch.delenv(key, raising=False)

    if session_home is not None:
        monkeypatch.setenv("MERIDIAN_HOME", session_home)
