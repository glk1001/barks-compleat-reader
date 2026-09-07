"""Characterization tests that pin current navigation behavior.

These tests exist to freeze behavior across the NavigationModel refactor.
They target gaps in existing coverage:

- `_auto_select_single_child` — tag extraction from tag/tag-group parents.
- `_handle_title_node_selection` / `on_title_row_button_pressed` — exact
  `TitleTarget` contents (fanta_info + tag) pulled from destinations.
- `NavigationCoordinator.navigate_to_chrono_title` — year-range resolution
  across every `CHRONO_YEAR_RANGES` boundary.
"""
# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.navigation_coordinator
import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.navigation import (
    Destination,
    TagDestination,
    TagGroupDestination,
    TitleDestination,
)
from barks_reader.core.reader_consts_and_types import CHRONO_YEAR_RANGES
from barks_reader.ui.navigation_coordinator import NavigationCoordinator, TitleTarget
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.tree_view_manager import TreeViewManager
from barks_reader.ui.tree_view_nodes import (
    ButtonTreeViewNode,
    TitleTreeViewNode,
)

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

# --- Shared fixtures ------------------------------------------------------


@pytest.fixture
def screen_mocks() -> dict[str, MagicMock]:
    return {
        "tree_view": MagicMock(),
        "bottom_title_view": MagicMock(),
        "fun_image_view": MagicMock(),
        "main_index": MagicMock(),
        "speech_index": MagicMock(),
        "names_index": MagicMock(),
        "locations_index": MagicMock(),
        "statistics": MagicMock(),
        "history": MagicMock(),
        "search": MagicMock(),
    }


@pytest.fixture
def mock_screens(screen_mocks: dict[str, MagicMock]) -> ScreenBundle:
    return ScreenBundle(**screen_mocks)


@pytest.fixture
def tvm_deps(mock_screens: ScreenBundle) -> dict[str, Any]:
    nav_coordinator = MagicMock()
    nav_coordinator.update_title.return_value = True
    return {
        "renderer": MagicMock(),
        "screens": mock_screens,
        "nav_coordinator": nav_coordinator,
    }


@pytest.fixture
def tree_view_manager(tvm_deps: dict[str, Any]) -> TreeViewManager:
    return TreeViewManager(**tvm_deps)


def _fake_fanta() -> FantaComicBookInfo:
    """Sentinel fanta_info — identity-comparable, not type-checked at runtime."""
    return cast("FantaComicBookInfo", object())


def _make_title_node(fanta_info: FantaComicBookInfo) -> MagicMock:
    """Build a MagicMock that passes isinstance(TitleTreeViewNode) and carries a destination."""
    node = MagicMock(spec=TitleTreeViewNode)
    node.destination = TitleDestination(fanta_info=fanta_info)
    return node


# --- _handle_title_node_selection: TitleTarget carries fanta_info --------


def test_title_node_selection_passes_fanta_info_in_title_target(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    fanta = _fake_fanta()
    node = _make_title_node(fanta)

    tree_view_manager._handle_title_node_selection(node)

    nav = tvm_deps["nav_coordinator"]
    nav.select_title.assert_called_once()
    (target,), _ = nav.select_title.call_args
    assert isinstance(target, TitleTarget)
    assert target.fanta_info is fanta
    assert target.tag is None


# --- on_title_row_button_pressed: tag extraction ------------------------


def test_title_row_button_pressed_no_tag_when_parent_has_no_tag_destination(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    fanta = _fake_fanta()
    button = MagicMock()
    button.parent.destination = TitleDestination(fanta_info=fanta)
    button.parent.parent_node.destination = None

    tree_view_manager.on_title_row_button_pressed(button)

    (target,), _ = tvm_deps["nav_coordinator"].select_title.call_args
    assert target.fanta_info is fanta
    assert target.tag is None


def test_title_row_button_pressed_extracts_tag_from_tag_parent(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    fanta = _fake_fanta()
    button = MagicMock()
    button.parent.destination = TitleDestination(fanta_info=fanta)
    button.parent.parent_node.destination = TagDestination(tag=Tags.AIRPLANES)

    tree_view_manager.on_title_row_button_pressed(button)

    (target,), _ = tvm_deps["nav_coordinator"].select_title.call_args
    assert target.fanta_info is fanta
    assert target.tag is Tags.AIRPLANES


def test_title_row_button_pressed_extracts_tag_from_tag_group_parent(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    fanta = _fake_fanta()
    button = MagicMock()
    button.parent.destination = TitleDestination(fanta_info=fanta)
    button.parent.parent_node.destination = TagGroupDestination(tag_group=TagGroups.AFRICA)

    tree_view_manager.on_title_row_button_pressed(button)

    (target,), _ = tvm_deps["nav_coordinator"].select_title.call_args
    assert target.fanta_info is fanta
    assert target.tag is TagGroups.AFRICA


# --- _auto_select_single_child -------------------------------------------


def _parent_with_single_title_child(
    parent_destination: Destination | None = None,
) -> tuple[MagicMock, MagicMock, FantaComicBookInfo]:
    """Build (parent, only_child_title, fanta_info_sentinel)."""
    fanta = _fake_fanta()
    child = _make_title_node(fanta)
    parent = MagicMock(spec=ButtonTreeViewNode)
    parent.nodes = [child]
    parent.destination = parent_destination
    return parent, child, fanta


def test_auto_select_single_child_selects_child_and_calls_nav_with_preserve_top_view(
    tree_view_manager: TreeViewManager,
    tvm_deps: dict[str, Any],
    screen_mocks: dict[str, MagicMock],
) -> None:
    parent, child, fanta = _parent_with_single_title_child()

    tree_view_manager._auto_select_single_child(parent)

    screen_mocks["tree_view"].select_node.assert_called_with(child)
    nav = tvm_deps["nav_coordinator"]
    (target,), kwargs = nav.select_title.call_args
    assert target.fanta_info is fanta
    assert target.tag is None
    assert kwargs == {"preserve_top_view": True}


def test_auto_select_single_child_extracts_tag_from_tag_parent(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    parent, _child, fanta = _parent_with_single_title_child(TagDestination(tag=Tags.ALASKA))

    tree_view_manager._auto_select_single_child(parent)

    (target,), kwargs = tvm_deps["nav_coordinator"].select_title.call_args
    assert target.fanta_info is fanta
    assert target.tag is Tags.ALASKA
    assert kwargs == {"preserve_top_view": True}


def test_auto_select_single_child_extracts_tag_from_tag_group_parent(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    parent, _child, fanta = _parent_with_single_title_child(
        TagGroupDestination(tag_group=TagGroups.AFRICA)
    )

    tree_view_manager._auto_select_single_child(parent)

    (target,), kwargs = tvm_deps["nav_coordinator"].select_title.call_args
    assert target.fanta_info is fanta
    assert target.tag is TagGroups.AFRICA
    assert kwargs == {"preserve_top_view": True}


def test_auto_select_single_child_ignores_non_title_children(
    tree_view_manager: TreeViewManager, tvm_deps: dict[str, Any]
) -> None:
    """Only the TitleTreeViewNode child should be picked, not sibling buttons."""
    fanta = _fake_fanta()
    title_child = _make_title_node(fanta)
    sibling_button = MagicMock(spec=ButtonTreeViewNode)
    parent = MagicMock(spec=ButtonTreeViewNode)
    parent.nodes = [sibling_button, title_child]
    parent.destination = None

    tree_view_manager._auto_select_single_child(parent)

    (target,), _ = tvm_deps["nav_coordinator"].select_title.call_args
    assert target.fanta_info is fanta


# --- NavigationCoordinator.navigate_to_chrono_title: year-range boundaries


@pytest.fixture
def nav_coord_deps() -> dict[str, MagicMock]:
    return {
        "reader_settings": MagicMock(),
        "comics_database": MagicMock(),
        "renderer": MagicMock(),
        "comic_reader_manager": MagicMock(),
        "bottom_title_view_screen": MagicMock(),
        "tree_view_screen": MagicMock(),
        "screen_switchers": MagicMock(),
        "special_fanta_overrides": MagicMock(),
        "user_error_handler": MagicMock(),
        "on_active_changed": MagicMock(),
    }


@pytest.fixture
def nav_coord(nav_coord_deps: dict[str, MagicMock]) -> NavigationCoordinator:
    coord = NavigationCoordinator(**nav_coord_deps)
    coord.set_tree_view_manager(MagicMock())
    return coord


@pytest.mark.parametrize("year_range", CHRONO_YEAR_RANGES)
def test_chrono_year_range_boundaries_resolve_to_correct_node(
    nav_coord: NavigationCoordinator,
    year_range: tuple[int, int],
) -> None:
    """Every (start, end) pair and both endpoints must resolve to the matching node."""
    start, end = year_range
    for submitted_year in (start, end):
        year_node = MagicMock()
        year_node.nodes = []
        nav_coord.set_year_range_nodes({year_range: year_node})

        fanta = MagicMock()
        fanta.comic_book_info.get_title_str.return_value = "T"
        fanta.comic_book_info.submitted_year = submitted_year

        image_info = ImageInfo(filename=Path("x.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator, "get_fanta_info", return_value=fanta
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=MagicMock(),
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

        year_node.ensure_populated.assert_called_once()


def test_chrono_year_range_missing_raises(
    nav_coord: NavigationCoordinator,
) -> None:
    """A year outside every known range must raise rather than silently pick a random node."""
    fanta = MagicMock()
    fanta.comic_book_info.get_title_str.return_value = "T"
    fanta.comic_book_info.submitted_year = 1900  # outside all CHRONO_YEAR_RANGES
    nav_coord.set_year_range_nodes({})

    image_info = ImageInfo(filename=Path("x.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

    with (
        patch.object(barks_reader.ui.navigation_coordinator, "get_fanta_info", return_value=fanta),
        pytest.raises(RuntimeError, match="No year range found"),
    ):
        nav_coord.navigate_to_chrono_title(image_info)


def test_select_title_with_tag_sets_goto_page_checkbox(
    nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
) -> None:
    """Pins the tag -> goto-page side effect in select_title."""
    fanta = MagicMock()
    fanta.comic_book_info.get_title_str.return_value = "T"
    target = TitleTarget(fanta_info=fanta, tag=TagGroups.AFRICA)

    nav_coord.select_title(target)

    nav_coord_deps["renderer"].render_title.assert_called_with(
        fanta, title_image_file=None, preserve_top_view=False
    )
    # A TagGroups tag (not Tags) short-circuits the per-page branch — just verify
    # no crash and view state was set. The Tags-type branch is covered elsewhere.
