"""Conftest that auto-skips Kivy-UI tests when no OpenGL context is available.

On a machine with no display server or GPU, Kivy cannot create an OpenGL window.
Tests that import from barks_reader.ui or kivy are skipped when the environment
variable KIVY_HEADLESS_CI is set. No CI runner sets it now: Linux draws on Xvfb,
Windows through ANGLE (Direct3D in software), and macOS on Apple's software
renderer through scripts/macos/with-soft-gl.sh; all three run them.
"""

from __future__ import annotations

import ast
import functools
import os
import sys
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Generator

    from barks_reader.ui.screen_bundle import ScreenBundle

_HEADLESS_CI = os.environ.get("KIVY_HEADLESS_CI", "") == "1"

# The tests run under ``--import-mode=importlib``, which puts no test directory on
# ``sys.path``, so a module beside the tests (``view_pipeline_factory``) is reached by
# putting the directory there, as the barks-fantagraphics tests do.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


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


@pytest.fixture
def screen_mocks() -> dict[str, MagicMock]:
    """Make a stand-in for each screen of the main screen, keyed as the ScreenBundle names it."""
    # Imported here, not at module scope: barks_reader.ui pulls Kivy in.
    from barks_reader.ui.screen_bundle import ScreenBundle  # noqa: PLC0415

    return {screen.name: MagicMock() for screen in fields(ScreenBundle)}


@pytest.fixture
def screens(screen_mocks: dict[str, MagicMock]) -> ScreenBundle:
    from barks_reader.ui.screen_bundle import ScreenBundle  # noqa: PLC0415

    return ScreenBundle(**screen_mocks)


_UI_IMPORT_PREFIXES = ("barks_reader.ui", "kivy")


@functools.cache
def _module_imports_ui(mod_file: str) -> bool:
    """Return True if the module at ``mod_file`` imports from ``barks_reader.ui`` or Kivy.

    Read from its import statements, at module scope or inside a test, so a mention
    in a comment or docstring does not count and a local import does.
    """
    try:
        tree = ast.parse(Path(mod_file).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        if any(name.startswith(_UI_IMPORT_PREFIXES) for name in names):
            return True
    return False


def _test_imports_ui(item: pytest.Item) -> bool:
    """Return True if the test's module imports Kivy UI code."""
    mod_file = getattr(getattr(item, "module", None), "__file__", None)
    return bool(mod_file) and _module_imports_ui(mod_file)


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
