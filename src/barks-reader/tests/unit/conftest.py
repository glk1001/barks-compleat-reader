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
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Generator

    from barks_reader.ui.navigation_coordinator import NavigationCoordinator
    from barks_reader.ui.screen_bundle import ScreenBundle
    from barks_reader.ui.tree_view_manager import TreeViewManager

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
def row_pinner_stub() -> MagicMock:
    """Return an index screen's row pinner stand-in that runs a press's action at once.

    The real one does too, holding the pressed row still over the frames after; a
    screen built without its kv has no scroll view for it to hold.
    """
    pinner = MagicMock()
    pinner.pin_row.side_effect = lambda _row, *, populate, **_kw: populate()
    return pinner


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

    mocks = {screen.name: MagicMock() for screen in fields(ScreenBundle)}
    for mock in mocks.values():
        mock.has_list_open_without_the_keys.return_value = False  # no list open by mouse
    return mocks


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


@pytest.fixture
def nav_coord_deps() -> dict[str, MagicMock]:
    """Make a stand-in for each collaborator a NavigationCoordinator is built with."""
    from barks_reader.core.ports import TitleViewChoices  # noqa: PLC0415

    # The title view as it opens: no page offered, the overrides in use.
    title_view = MagicMock()
    title_view.choices.return_value = TitleViewChoices(
        goto_page_active=False, goto_page_num="", tagged_pages=(), use_overrides_active=True
    )
    return {
        "reader_settings": MagicMock(),
        "comics_database": MagicMock(),
        "renderer": MagicMock(),
        "comic_reader_manager": MagicMock(),
        "bottom_title_view_screen": title_view,
        "screen_switchers": MagicMock(),
        "special_fanta_overrides": MagicMock(),
        "user_error_handler": MagicMock(),
        "on_active_changed": MagicMock(),
    }


@pytest.fixture
def nav_coord(nav_coord_deps: dict[str, MagicMock]) -> NavigationCoordinator:
    """Make a NavigationCoordinator over `nav_coord_deps`, with a stand-in tree manager."""
    from barks_reader.ui.navigation_coordinator import NavigationCoordinator  # noqa: PLC0415

    coord = NavigationCoordinator(**nav_coord_deps)
    coord.set_tree_view_manager(MagicMock())
    return coord


@pytest.fixture
def tree_view_manager_deps(screens: ScreenBundle) -> dict[str, Any]:
    """Make what a TreeViewManager is built with: the screen bundle and two stand-ins."""
    return {"renderer": MagicMock(), "screens": screens, "nav_coordinator": MagicMock()}


@pytest.fixture
def tree_view_manager(tree_view_manager_deps: dict[str, Any]) -> TreeViewManager:
    """Make a TreeViewManager over `tree_view_manager_deps`."""
    from barks_reader.ui.tree_view_manager import TreeViewManager  # noqa: PLC0415

    return TreeViewManager(**tree_view_manager_deps)


@pytest.fixture
def bg_color_label() -> Generator[None]:
    """Register a stand-in for the app's BgColorLabel, which main_screen.kv defines.

    That kv file is not loaded in a unit test, and an overlay's own kv rule names
    the class.
    """
    from kivy.factory import Factory  # noqa: PLC0415
    from kivy.properties import (  # noqa: PLC0415  # ty: ignore[import-not-found]
        ColorProperty,
        NumericProperty,
    )
    from kivy.uix.label import Label  # noqa: PLC0415

    if "BgColorLabel" in Factory.classes:
        yield
        return

    class BgColorLabel(Label):
        background_color = ColorProperty((0, 0, 0, 0))
        sizing_factor_x = NumericProperty(1.0)

    Factory.register("BgColorLabel", cls=BgColorLabel)
    yield
    Factory.unregister("BgColorLabel")


@pytest.fixture
def index_settings() -> MagicMock:
    """Make the settings a speech or entity index screen reads when it is built."""
    settings = MagicMock()
    settings.file_paths.barks_panels_are_encrypted = False
    settings.sys_file_paths.get_barks_reader_indexes_dir.return_value = "indexes_dir"
    return settings


@pytest.fixture
def speech_index_patches() -> Generator[SimpleNamespace]:
    """Patch what a SpeechIndexScreen (and so an entity one) builds, so no kv file is needed.

    Yields the three patched classes a test reads back: `search_cls`, `image_selector_cls`
    and `texture_loader_cls`. The alphabet menu and `ids` are the test's own to patch:
    they sit on whichever screen class it builds.
    """
    import barks_reader.ui.index_screen  # noqa: PLC0415
    import barks_reader.ui.speech_index_screen as module  # noqa: PLC0415

    with (
        patch.object(barks_reader.ui.index_screen.IndexScreen, "__init__"),
        patch.object(module, "ComicSearch") as search_cls,
        patch.object(module, "ImageSelector") as image_selector_cls,
        patch.object(module, "ReaderFilePathsResolver"),
        patch.object(module, "PanelTextureLoader") as texture_loader_cls,
        patch.object(module, "create_speech_bubble_popup", return_value=(MagicMock(), MagicMock())),
    ):
        yield SimpleNamespace(
            search_cls=search_cls,
            image_selector_cls=image_selector_cls,
            texture_loader_cls=texture_loader_cls,
        )
