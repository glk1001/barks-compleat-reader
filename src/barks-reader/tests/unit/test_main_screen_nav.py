# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import main_screen_nav as nav_module
from barks_reader.ui.main_screen_nav import MainScreenNavigation
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
)
from barks_reader.ui.reader_ui_classes import ButtonTreeViewNode, TitleTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def screens() -> dict[str, MagicMock]:
    return {
        "tree_view_screen": MagicMock(),
        "tree_view_manager": MagicMock(),
        "bottom_title_view_screen": MagicMock(),
        "fun_image_view_screen": MagicMock(),
        "main_index_screen": MagicMock(),
        "speech_index_screen": MagicMock(),
        "names_index_screen": MagicMock(),
        "locations_index_screen": MagicMock(),
        "statistics_screen": MagicMock(),
        "search_screen": MagicMock(),
        "bottom_base_view_screen": MagicMock(),
    }


@pytest.fixture
def nav(screens: dict[str, MagicMock]) -> Generator[MainScreenNavigation]:
    on_title_activated = MagicMock()
    enter_menu_mode = MagicMock()
    handle_menu_key = MagicMock(return_value=True)
    is_in_menu_mode = MagicMock(return_value=False)

    with (
        patch.object(nav_module, "draw_focus_highlight"),
        patch.object(nav_module, "clear_focus_highlight"),
    ):
        n = MainScreenNavigation(
            **screens,
            on_title_activated=on_title_activated,
            enter_menu_mode=enter_menu_mode,
            handle_menu_key=handle_menu_key,
            is_in_menu_mode=is_in_menu_mode,
        )
        yield n


class TestHandleKey:
    def test_delegates_to_menu_when_in_menu_mode(self, nav: MainScreenNavigation) -> None:
        nav._is_in_menu_mode.return_value = True
        nav._handle_menu_key.return_value = True

        assert nav.handle_key(KEY_ENTER) is True
        nav._handle_menu_key.assert_called_once_with(KEY_ENTER)

    def test_delegates_to_tree_key_by_default(self, nav: MainScreenNavigation) -> None:
        result = nav.handle_key(KEY_ESCAPE)

        assert result is True
        nav._enter_menu_mode.assert_called_once()

    def test_delegates_to_bottom_key_when_in_bottom_focus(self, nav: MainScreenNavigation) -> None:
        # Set up: no visible screens so bottom key falls through to fun/title checks
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        # TAB should exit bottom focus
        result = nav.handle_key(KEY_TAB)
        assert result is True
        assert nav._focus_region.name == "TREE"


class TestHandleTreeKey:
    def test_escape_enters_menu_mode(self, nav: MainScreenNavigation) -> None:
        assert nav._handle_tree_key(KEY_ESCAPE) is True
        nav._enter_menu_mode.assert_called_once()

    def test_tab_enters_bottom_focus(self, nav: MainScreenNavigation) -> None:
        # Make at least one bottom screen visible
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._handle_tree_key(KEY_TAB) is True
        assert nav.is_in_bottom_focus

    def test_up_moves_tree(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_visible_nodes.return_value = [MagicMock(), MagicMock()]
        nav._tree_view_screen.get_selected_node.return_value = None

        assert nav._handle_tree_key(KEY_UP) is True
        nav._tree_view_screen.select_node.assert_called_once()

    def test_down_moves_tree(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_visible_nodes.return_value = [MagicMock(), MagicMock()]
        nav._tree_view_screen.get_selected_node.return_value = None

        assert nav._handle_tree_key(KEY_DOWN) is True
        nav._tree_view_screen.select_node.assert_called_once()

    def test_left_collapses(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None

        assert nav._handle_tree_key(KEY_LEFT) is True

    def test_enter_activates(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None

        assert nav._handle_tree_key(KEY_ENTER) is True

    def test_numpad_enter_activates(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None

        assert nav._handle_tree_key(KEY_NUMPAD_ENTER) is True

    def test_unhandled_key_returns_false(self, nav: MainScreenNavigation) -> None:
        assert nav._handle_tree_key(999) is False


class TestHandleBottomKey:
    def test_tab_exits_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM
        # No active nav screen
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_TAB) is True
        assert not nav.is_in_bottom_focus

    def test_escape_exits_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_ESCAPE) is True
        assert not nav.is_in_bottom_focus

    def test_delegates_to_nav_screen(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = True
        nav._main_index_screen.handle_key.return_value = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_DOWN) is True
        nav._main_index_screen.handle_key.assert_called_once_with(KEY_DOWN)

    def test_tab_on_nav_screen_exits(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)
        nav._main_index_screen.is_visible = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_TAB) is True
        nav._main_index_screen.exit_nav_focus.assert_called_once()

    def test_fun_view_left_right(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_LEFT) is True
        nav._fun_image_view_screen.prev_image.assert_called_once()

        assert nav._handle_bottom_key(KEY_RIGHT) is True
        nav._fun_image_view_screen.next_image.assert_called_once()

    def test_title_view_enter(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True

        assert nav._handle_bottom_key(KEY_ENTER) is True
        nav._on_title_activated.assert_called_once()


class TestTreeNavMove:
    def test_no_visible_nodes(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_visible_nodes.return_value = []

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_not_called()

    def test_no_selection_delta_positive(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes
        nav._tree_view_screen.get_selected_node.return_value = None

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[0])

    def test_no_selection_delta_negative(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes
        nav._tree_view_screen.get_selected_node.return_value = None

        nav._tree_nav_move(-1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[2])

    def test_move_down_from_middle(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes
        nav._tree_view_screen.get_selected_node.return_value = nodes[1]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[2])
        nav._tree_view_screen.scroll_to_node.assert_called_with(nodes[2])

    def test_clamps_at_end(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes
        nav._tree_view_screen.get_selected_node.return_value = nodes[1]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[1])

    def test_activates_title_node(self, nav: MainScreenNavigation) -> None:
        title_node = MagicMock(spec=TitleTreeViewNode)
        nav._tree_view_screen.get_visible_nodes.return_value = [title_node]
        nav._tree_view_screen.get_selected_node.return_value = None

        nav._tree_nav_move(1)

        nav._tree_view_manager.activate_node.assert_called_with(title_node)


class TestTreeNavActivate:
    def test_no_selection_does_nothing(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None

        nav._tree_nav_activate()

        nav._tree_view_manager.activate_node.assert_not_called()

    def test_title_node_calls_on_title_activated(self, nav: MainScreenNavigation) -> None:
        selected = MagicMock(spec=TitleTreeViewNode)
        nav._tree_view_screen.get_selected_node.return_value = selected

        with patch.object(nav_module, "Clock"):
            nav._tree_nav_activate()

        nav._tree_view_manager.activate_node.assert_called_with(selected)
        nav._on_title_activated.assert_called_once()

    def test_index_node_enters_bottom_focus(self, nav: MainScreenNavigation) -> None:
        node = MagicMock()
        nav._main_index_screen.treeview_index_node = node
        nav._speech_index_screen.treeview_index_node = MagicMock()
        nav._names_index_screen.treeview_index_node = MagicMock()
        nav._locations_index_screen.treeview_index_node = MagicMock()
        nav._tree_view_manager.speech_words_node = MagicMock()
        nav._tree_view_manager.statistics_node = MagicMock()
        nav._tree_view_screen.get_selected_node.return_value = node
        nav._main_index_screen.is_visible = True

        with patch.object(nav_module, "Clock"):
            nav._tree_nav_activate()

        # Should have entered bottom focus since screen is visible
        assert nav.is_in_bottom_focus

    def test_button_node_opens_and_selects_first_child(self, nav: MainScreenNavigation) -> None:
        selected = MagicMock(spec=ButtonTreeViewNode)
        selected.is_open = False
        selected.nodes = [MagicMock()]
        nav._tree_view_screen.get_selected_node.return_value = selected
        nav._main_index_screen.treeview_index_node = MagicMock()
        nav._speech_index_screen.treeview_index_node = MagicMock()
        nav._names_index_screen.treeview_index_node = MagicMock()
        nav._locations_index_screen.treeview_index_node = MagicMock()
        nav._tree_view_manager.speech_words_node = MagicMock()
        nav._tree_view_manager.statistics_node = MagicMock()
        nav._search_screen.is_visible = False

        with patch.object(nav_module, "Clock") as mock_clock:
            nav._tree_nav_activate()

        nav._tree_view_manager.activate_node.assert_called_with(selected)
        mock_clock.schedule_once.assert_called_once()


class TestTreeNavCollapseToParent:
    def test_no_selection(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_manager.activate_node.assert_not_called()

    def test_open_button_node_collapses(self, nav: MainScreenNavigation) -> None:
        selected = MagicMock(spec=ButtonTreeViewNode)
        selected.is_open = True
        selected.nodes = [MagicMock()]
        nav._tree_view_screen.get_selected_node.return_value = selected

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_manager.activate_node.assert_called_with(selected)

    def test_child_node_selects_parent(self, nav: MainScreenNavigation) -> None:
        parent = MagicMock(spec=ButtonTreeViewNode)
        parent.is_open = True
        selected = MagicMock()
        selected.parent_node = parent
        nav._tree_view_screen.get_selected_node.return_value = selected

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_manager.activate_node.assert_called_with(parent)
        nav._tree_view_screen.scroll_to_node.assert_called_with(parent)

    def test_child_with_closed_parent_selects_without_activating(
        self, nav: MainScreenNavigation
    ) -> None:
        parent = MagicMock(spec=ButtonTreeViewNode)
        parent.is_open = False
        selected = MagicMock()
        selected.parent_node = parent
        nav._tree_view_screen.get_selected_node.return_value = selected

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_screen.select_node.assert_called_with(parent)
        nav._tree_view_screen.scroll_to_node.assert_called_with(parent)


class TestFocusSaveRestore:
    def test_save_and_restore_tree(self, nav: MainScreenNavigation) -> None:
        nav.save_focus_before_comic()
        nav.restore_focus_after_comic()

        assert not nav.is_in_bottom_focus
        assert nav._focus_region_before_comic is None

    def test_save_and_restore_bottom(self, nav: MainScreenNavigation) -> None:
        # Enter bottom focus
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav.enter_bottom_focus()

        nav.save_focus_before_comic()
        # Simulate leaving bottom during comic
        nav.exit_bottom_focus()

        nav.restore_focus_after_comic()
        assert nav.is_in_bottom_focus


class TestEnterBottomFocus:
    def test_nothing_visible_stays_in_tree(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.enter_bottom_focus()

        assert not nav.is_in_bottom_focus

    def test_nav_screen_gets_enter_nav_focus(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.enter_bottom_focus()

        nav._main_index_screen.enter_nav_focus.assert_called_once()


class TestGetActiveNavScreen:
    def test_returns_none_when_nothing_visible(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._get_active_nav_screen() is None

    def test_returns_first_visible(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = True
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._get_active_nav_screen() is nav._speech_index_screen


class TestEnterBottomFocusIfIndexVisible:
    def test_search_screen_visible(self, nav: MainScreenNavigation) -> None:
        nav._search_screen.is_visible = True
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible()

        assert nav.is_in_bottom_focus
        nav._search_screen.enter_nav_focus_at_last_result.assert_called_once()

    def test_index_screen_visible(self, nav: MainScreenNavigation) -> None:
        nav._search_screen.is_visible = False
        nav._main_index_screen.is_visible = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._statistics_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible()

        assert nav.is_in_bottom_focus

    def test_nothing_visible_does_nothing(self, nav: MainScreenNavigation) -> None:
        nav._search_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible()

        assert not nav.is_in_bottom_focus
