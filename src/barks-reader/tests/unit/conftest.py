"""Conftest that auto-skips Kivy-UI tests when no OpenGL context is available.

On a machine with no display server or GPU, Kivy cannot create an OpenGL window.
Tests that import from barks_reader.ui or kivy are skipped when the environment
variable KIVY_HEADLESS_CI is set. No CI runner sets it now: Linux draws on Xvfb,
Windows through ANGLE (Direct3D in software), and macOS on Apple's software
renderer through scripts/macos/with-soft-gl.sh; all three run them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Generator

_HEADLESS_CI = os.environ.get("KIVY_HEADLESS_CI", "") == "1"


@pytest.fixture(autouse=True)
def _no_layout_settling() -> Generator[None]:
    """Start and end every test with nothing moving the layout on purpose.

    ``barks_reader.core.tap_targets`` keeps a process-wide set of the work that
    is (the tree's scroll pinner); a test that starts a pin and never runs its
    settle loop to the end would leave it set for every test after.
    """
    from barks_reader.core import tap_targets  # noqa: PLC0415

    tap_targets._SETTLING.clear()  # noqa: SLF001
    yield
    tap_targets._SETTLING.clear()  # noqa: SLF001


@pytest.fixture
def mock_font_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture
def loguru_sink() -> Generator[list[str]]:
    """Collect every loguru message emitted during the test, DEBUG and up.

    The app's log is the oracle the GUI path tests wait on, so the lines that
    mark a transition are part of a screen's contract; a test asserts that one
    was emitted with ``assert "..." in loguru_sink``.
    """
    records: list[str] = []
    handle = logger.add(
        lambda message: records.append(str(message).rstrip("\n")),
        level="DEBUG",
        format="{message}",
    )
    try:
        yield records
    finally:
        logger.remove(handle)


@pytest.fixture
def mock_user_error_handler() -> MagicMock:
    return MagicMock()


_UI_IMPORT_PREFIXES = ("barks_reader.ui", "kivy.uix", "kivy.core.window")


def _test_imports_ui(item: pytest.Item) -> bool:
    """Return True if the test's module imports Kivy UI code."""
    module = getattr(item, "module", None)
    if module is None:
        return False
    # Check the module's direct imports (already loaded into sys.modules).
    for name in list(sys.modules):
        if any(name.startswith(prefix) for prefix in _UI_IMPORT_PREFIXES):
            # The module itself might not be the one importing UI code,
            # but checking the test file's source is more reliable.
            break
    else:
        return False

    # More precise: check the test file's own imports.
    mod_file = getattr(module, "__file__", "") or ""
    try:
        with Path(mod_file).open(encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return False
    return any(prefix in source for prefix in ("from barks_reader.ui", "from kivy"))


# noinspection PyUnusedLocal
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # noqa: ARG001
    """Skip UI tests on headless CI where Kivy cannot create an OpenGL context."""
    if not _HEADLESS_CI:
        return

    skip_marker = pytest.mark.skip(reason="Kivy UI tests skipped on headless CI (no OpenGL)")
    for item in items:
        # A test that imports UI code but never opens a Kivy window (the live Win32
        # backend test drives a window it makes itself) says so, and still runs.
        if item.get_closest_marker("needs_no_opengl") is not None:
            continue
        if _test_imports_ui(item):
            item.add_marker(skip_marker)
