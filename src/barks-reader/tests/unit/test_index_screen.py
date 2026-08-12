# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import pytest
from barks_reader.core.image_selector import ImageInfo
from barks_reader.ui.index_screen import (
    KEY_DOWN,
    SAVED_NODE_STATE_FIRST_LETTER_KEY,
    IndexItem,
    IndexItemButton,
    IndexMenuButton,
    IndexScreen,
    PopupKeyboardNav,
)
from barks_reader.ui.tree_view_nodes import MainTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.button import Button


# Create a concrete implementation for testing
class ConcreteIndexScreen(IndexScreen):
    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        # IndexScreen expects _font_manager to be available (usually set by subclasses)
        self._font_manager = MagicMock()

    def _new_index_image(self) -> None:
        pass

    def _create_index_button(self, item: Any) -> IndexItemButton:  # noqa: ANN401
        # Return a mock instead of a real widget
        btn = MagicMock(spec=IndexItemButton)
        btn.text = str(item)
        return btn

    def _get_no_items_button(self, letter: str) -> IndexItemButton:
        # Return a mock instead of a real widget
        btn = MagicMock(spec=IndexItemButton)
        btn.text = f"*** No index items for '{letter}' ***"
        return btn

    def _cancel_index_image_change_events(self) -> None:
        pass

    def _get_items_for_letter(self, first_letter: str) -> list[IndexItem]:
        if first_letter == "A":
            return [
                IndexItem(id="Apple", display_text="Apple"),
                IndexItem(id="Ant", display_text="Ant"),
            ]
        return []

    def _populate_index_for_letter(self, first_letter: str) -> None:
        self._populate_index_grid(first_letter)


@pytest.fixture
def mock_app() -> Generator[MagicMock]:
    with patch.object(barks_reader.ui.index_screen.App, "get_running_app") as mock_get_app:
        mock_app_instance = MagicMock()
        mock_get_app.return_value = mock_app_instance
        yield mock_app_instance


@pytest.fixture
def index_screen(mock_app: MagicMock) -> ConcreteIndexScreen:  # noqa: ARG001
    # Patch IndexMenuButton and IndexItemButton to avoid instantiation of Kivy widgets
    with (
        patch.object(barks_reader.ui.index_screen, "IndexMenuButton") as mock_menu_btn_cls,
        patch.object(barks_reader.ui.index_screen, "IndexItemButton") as mock_item_btn_cls,
    ):
        # Configure mock menu button
        def create_menu_btn(text: str | None = None) -> MagicMock:
            btn = MagicMock(spec=IndexMenuButton)
            btn.text = text
            return btn

        mock_menu_btn_cls.side_effect = create_menu_btn

        # Configure mock item button (for _get_no_items_button)
        def create_item_btn(text: str | None = None, **_kwargs: Any) -> MagicMock:  # noqa: ANN401
            btn = MagicMock(spec=IndexItemButton)
            btn.text = text
            return btn

        mock_item_btn_cls.side_effect = create_item_btn

        screen = ConcreteIndexScreen()

        # Manually set ids since we bypassed KV loading
        screen.ids = MagicMock()
        screen.ids.alphabet_side_layout = MagicMock()
        screen.ids.left_column_layout = MagicMock()
        screen.ids.middle_column_layout = MagicMock()
        screen.ids.right_column_layout = MagicMock()
        screen.ids.index_scroll_view = MagicMock()

        # Mock treeview_index_node
        screen.treeview_index_node = MagicMock(spec=MainTreeViewNode)
        screen.treeview_index_node.saved_state = {}

        return screen


class TestIndexScreen:
    def test_init(self, index_screen: ConcreteIndexScreen) -> None:
        assert index_screen.index_theme is not None
        assert index_screen._alphabet_buttons == {}

    def test_populate_alphabet_menu(self, index_screen: ConcreteIndexScreen) -> None:
        index_screen._populate_alphabet_menu()

        # Check if buttons were added to alphabet_side_layout
        # 0 + ' + A-Z = 28 buttons
        assert index_screen.ids.alphabet_side_layout.add_widget.call_count == 28
        assert "A" in index_screen._alphabet_buttons
        assert "Z" in index_screen._alphabet_buttons
        assert "0" in index_screen._alphabet_buttons
        assert "'" in index_screen._alphabet_buttons

    def test_on_letter_press(self, index_screen: ConcreteIndexScreen) -> None:
        index_screen._populate_alphabet_menu()
        button_a = index_screen._alphabet_buttons["A"]

        with patch.object(index_screen, "_populate_index_for_letter") as mock_populate:
            index_screen.on_letter_press(button_a)

            assert index_screen.treeview_index_node is not None
            assert (
                index_screen.treeview_index_node.saved_state[SAVED_NODE_STATE_FIRST_LETTER_KEY]
                == "A"
            )
            assert button_a.is_selected is True
            assert index_screen._selected_letter_button == button_a
            mock_populate.assert_called_with("A")

    def test_populate_index_grid(self, index_screen: ConcreteIndexScreen) -> None:
        # Setup
        index_screen.ids.left_column_layout.clear_widgets = MagicMock()
        index_screen.ids.right_column_layout.clear_widgets = MagicMock()
        index_screen.ids.middle_column_layout.clear_widgets = MagicMock()

        # Test with items (Letter A returns ["Apple", "Ant"])
        index_screen._populate_index_grid("A")

        index_screen.ids.left_column_layout.clear_widgets.assert_called_once()
        index_screen.ids.right_column_layout.clear_widgets.assert_called_once()

        # 2 items. Split point (2+1)//2 = 1.
        # Left: Apple. Right: Ant.
        assert index_screen.ids.left_column_layout.add_widget.call_count == 1
        assert index_screen.ids.right_column_layout.add_widget.call_count == 1

        # Test with no items
        index_screen.ids.left_column_layout.reset_mock()
        index_screen.ids.right_column_layout.reset_mock()
        index_screen.ids.middle_column_layout.reset_mock()

        index_screen._populate_index_grid("Z")  # Returns []

        # Should add "No items" button to left column
        assert index_screen.ids.left_column_layout.add_widget.call_count == 1
        # Check text of added widget
        args, _ = index_screen.ids.left_column_layout.add_widget.call_args
        assert "*** No index items for 'Z' ***" in args[0].text

    def test_on_is_visible_true(self, index_screen: ConcreteIndexScreen) -> None:
        index_screen._populate_alphabet_menu()

        # Case 1: No selected button, no saved state -> Default 'A'
        with patch.object(index_screen, "on_letter_press") as mock_press:
            index_screen.on_is_visible(index_screen, value=True)
            mock_press.assert_called_with(index_screen._alphabet_buttons["A"])

        # Case 2: Saved state exists
        assert index_screen.treeview_index_node is not None
        index_screen.treeview_index_node.saved_state[SAVED_NODE_STATE_FIRST_LETTER_KEY] = "B"
        with patch.object(index_screen, "on_letter_press") as mock_press:
            index_screen.on_is_visible(index_screen, value=True)
            mock_press.assert_called_with(index_screen._alphabet_buttons["B"])

        # Case 3: Already selected button
        index_screen._selected_letter_button = index_screen._alphabet_buttons["C"]
        with patch.object(index_screen, "_new_index_image") as mock_new_image:
            index_screen.on_is_visible(index_screen, value=True)
            mock_new_image.assert_called_once()

    def test_on_is_visible_false(self, index_screen: ConcreteIndexScreen) -> None:
        with patch.object(index_screen, "_cancel_index_image_change_events") as mock_cancel:
            index_screen.on_is_visible(index_screen, value=False)
            mock_cancel.assert_called_once()

    def test_get_sortable_string(self, index_screen: ConcreteIndexScreen) -> None:
        assert index_screen._get_sortable_string("The Apple") == "Apple, The"
        assert index_screen._get_sortable_string("A Banana") == "Banana, A"
        assert index_screen._get_sortable_string("Carrot") == "Carrot"

    def test_resync_item_focus_first_expand(self, index_screen: ConcreteIndexScreen) -> None:
        """First expansion: no prior sub-items, count increases, focus moves to first sub-item."""
        parent_btn = MagicMock(spec=IndexItemButton)
        sub_item_btn = MagicMock(spec=IndexItemButton)

        # After expansion the column has [parent_btn, sub_item_btn, other_btn].
        col_buttons = [parent_btn, sub_item_btn, MagicMock(spec=IndexItemButton)]
        with patch.object(index_screen, "_get_col_buttons", return_value=col_buttons):
            index_screen._nav_active = True
            index_screen._nav_panel = barks_reader.ui.index_screen._IndexNavPanel.ITEMS
            index_screen._nav_focused_col = 0
            index_screen._nav_focused_item_idx = 0

            # old_count=2 (before expansion), now 3 buttons → expansion detected.
            index_screen._resync_item_focus(parent_btn, old_count=2)

            assert index_screen._nav_focused_item_idx == 1

    def test_resync_item_focus_switch_expand(self, index_screen: ConcreteIndexScreen) -> None:
        """Second expansion after switching items: old sub-items removed then new ones added.

        The parent button's position shifts after old sub-items above it are removed,
        so resync must locate the button's current index before adding 1.
        """
        btn_a = MagicMock(spec=IndexItemButton)
        btn_b = MagicMock(spec=IndexItemButton)  # The button we just expanded.
        new_sub = MagicMock(spec=IndexItemButton)

        # After old sub-items removed and new ones added: [btn_a, btn_b, new_sub].
        col_buttons = [btn_a, btn_b, new_sub]
        with patch.object(index_screen, "_get_col_buttons", return_value=col_buttons):
            index_screen._nav_active = True
            index_screen._nav_panel = barks_reader.ui.index_screen._IndexNavPanel.ITEMS
            index_screen._nav_focused_col = 0
            # Stale index from before the synchronous removal shifted positions.
            index_screen._nav_focused_item_idx = 5

            # old_count=2 (post-removal, pre-addition), now 3 → expansion detected.
            index_screen._resync_item_focus(btn_b, old_count=2)

            # Focus should land on new_sub (btn_b is at index 1, so first sub-item is 2).
            assert index_screen._nav_focused_item_idx == 2

    def test_resync_item_focus_collapse(self, index_screen: ConcreteIndexScreen) -> None:
        """Collapse: count unchanged or decreased, focus stays on the parent button."""
        btn_a = MagicMock(spec=IndexItemButton)
        btn_b = MagicMock(spec=IndexItemButton)

        col_buttons = [btn_a, btn_b]
        with patch.object(index_screen, "_get_col_buttons", return_value=col_buttons):
            index_screen._nav_active = True
            index_screen._nav_panel = barks_reader.ui.index_screen._IndexNavPanel.ITEMS
            index_screen._nav_focused_col = 0
            index_screen._nav_focused_item_idx = 0

            # old_count=3, now 2 → collapse.
            index_screen._resync_item_focus(btn_a, old_count=3)

            assert index_screen._nav_focused_item_idx == 0

    def test_on_goto_background_title(self, index_screen: ConcreteIndexScreen) -> None:
        mock_func = MagicMock()
        index_screen.on_goto_background_title_func = mock_func

        # No image info
        index_screen._current_image_info = None
        index_screen.on_goto_background_title()
        mock_func.assert_not_called()

        # With image info
        info = ImageInfo()
        index_screen._current_image_info = info
        index_screen.on_goto_background_title()
        mock_func.assert_called_with(info)


class TestPopupKeyboardNavWindowBinding:
    """The speech-bubble popup owns the keyboard via its own Window binding.

    The main screen yields to the modal popup (see `_modal_popup_is_open`), so the
    nav helper must bind `Window.on_key_down` itself to receive keys while open.
    """

    @staticmethod
    def _make_nav() -> PopupKeyboardNav:
        return PopupKeyboardNav(MagicMock())

    def test_on_opened_binds_window_key_handler(self) -> None:
        nav = self._make_nav()
        with (
            patch.object(barks_reader.ui.index_screen, "Window") as window,
            patch.object(barks_reader.ui.index_screen, "Clock"),
        ):
            nav._on_opened()

        window.bind.assert_called_once_with(on_key_down=nav._on_key_down)

    def test_on_dismissed_unbinds_window_key_handler(self) -> None:
        nav = self._make_nav()
        with (
            patch.object(barks_reader.ui.index_screen, "Window") as window,
            patch.object(PopupKeyboardNav, "_clear_focus"),
        ):
            nav._on_dismissed()

        window.unbind.assert_called_once_with(on_key_down=nav._on_key_down)

    def test_on_key_down_delegates_to_handle_key_and_consumes(self) -> None:
        nav = self._make_nav()
        with patch.object(PopupKeyboardNav, "handle_key") as handle_key:
            consumed = nav._on_key_down(object(), KEY_DOWN, 0, "", [])

        handle_key.assert_called_once_with(KEY_DOWN)
        # Every key is consumed while the popup is modal, so nothing leaks.
        assert consumed is True


class _FakeWidget:
    """Minimal stand-in for a Kivy widget in the expand/collapse state machine."""

    def __init__(self, parent: _FakeWidget | None = None, owner_button: object = None) -> None:
        self.parent = parent
        self.owner_button = owner_button

    def remove_widget(self, widget: _FakeWidget) -> None:
        widget.parent = None


class TestSplitItems:
    """The column split must keep dealing items exactly as it always has."""

    @staticmethod
    def _old_three_column_bounds(num: int) -> list[tuple[int, int]]:
        split1 = (num + 2) // 3
        split2 = split1 + (num - split1 + 1) // 2
        return [(0, split1), (split1, split2), (split2, num)]

    @staticmethod
    def _old_two_column_bounds(num: int) -> list[tuple[int, int]]:
        split_point = (num + 1) // 2
        return [(0, split_point), (split_point, num)]

    @pytest.mark.parametrize("num_columns", [2, 3])
    @pytest.mark.parametrize("num_items", range(21))
    def test_matches_the_original_formulas(
        self, index_screen: ConcreteIndexScreen, num_columns: int, num_items: int
    ) -> None:
        index_screen.num_columns = num_columns
        items = [IndexItem(id=f"i{n}", display_text=f"i{n}") for n in range(num_items)]

        columns = index_screen._split_items(items)

        expected_bounds = (
            self._old_three_column_bounds(num_items)
            if num_columns == 3
            else self._old_two_column_bounds(num_items)
        )
        assert columns == [items[start:end] for start, end in expected_bounds]

    @pytest.mark.parametrize("num_columns", [2, 3])
    def test_deals_every_item_exactly_once(
        self, index_screen: ConcreteIndexScreen, num_columns: int
    ) -> None:
        index_screen.num_columns = num_columns
        items = [IndexItem(id=f"i{n}", display_text=f"i{n}") for n in range(17)]

        columns = index_screen._split_items(items)

        assert len(columns) == num_columns
        assert [item for column in columns for item in column] == items


class TestExpansionStateMachine:
    def test_clicking_the_owning_button_again_is_a_collapse(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        button = MagicMock()
        container = _FakeWidget(owner_button=button)
        index_screen._open_tag_widgets = [container]

        is_collapse, level = index_screen._get_level_of_click_for_collapse(button)

        assert is_collapse is True
        assert level == 0

    def test_clicking_a_different_button_is_not_a_collapse(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        container = _FakeWidget(owner_button=MagicMock())
        index_screen._open_tag_widgets = [container]

        is_collapse, level = index_screen._get_level_of_click_for_collapse(MagicMock())

        assert is_collapse is False
        assert level == -1

    def test_collapse_closes_the_level_and_everything_below_it(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        parent = _FakeWidget()
        outer, middle, inner = (_FakeWidget(parent=parent) for _ in range(3))
        index_screen._open_tag_widgets = [outer, middle, inner]

        index_screen._handle_collapse(1)

        assert index_screen._open_tag_widgets == [outer]
        assert middle.parent is None
        assert inner.parent is None
        assert outer.parent is parent

    def test_switching_to_a_top_level_item_closes_everything(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        parent = _FakeWidget()
        outer, inner = (_FakeWidget(parent=parent) for _ in range(2))
        index_screen._open_tag_widgets = [outer, inner]
        # A button that is not inside any open container.
        unrelated_button = _FakeWidget(parent=_FakeWidget())

        index_screen._handle_expand_or_switch(cast("Button", unrelated_button))

        assert index_screen._open_tag_widgets == []

    def test_drilling_down_keeps_the_containers_above_the_click(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        parent = _FakeWidget()
        outer = _FakeWidget(parent=parent)
        inner = _FakeWidget(parent=parent)
        index_screen._open_tag_widgets = [outer, inner]
        # A button living inside the outer container.
        button_in_outer = _FakeWidget(parent=outer)

        index_screen._handle_expand_or_switch(cast("Button", button_in_outer))

        assert index_screen._open_tag_widgets == [outer]
        assert inner.parent is None


class TestOnIndexItemPress:
    def test_terminal_item_short_circuits_before_any_expansion(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        item = IndexItem(id="Apple", display_text="Apple")
        with (
            patch.object(ConcreteIndexScreen, "_handle_terminal_item", return_value=True),
            patch.object(ConcreteIndexScreen, "_handle_expand_or_switch") as expand,
            patch.object(ConcreteIndexScreen, "_handle_item_expansion") as expansion,
        ):
            index_screen._on_index_item_press(MagicMock(), item)

        expand.assert_not_called()
        expansion.assert_not_called()

    def test_collapse_short_circuits_before_expansion(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        item = IndexItem(id="Apple", display_text="Apple")
        with (
            patch.object(
                ConcreteIndexScreen, "_get_level_of_click_for_collapse", return_value=(True, 0)
            ),
            patch.object(ConcreteIndexScreen, "_handle_collapse") as collapse,
            patch.object(ConcreteIndexScreen, "_handle_item_expansion") as expansion,
        ):
            index_screen._on_index_item_press(MagicMock(), item)

        collapse.assert_called_once_with(0)
        expansion.assert_not_called()

    def test_expand_cleans_up_then_expands(self, index_screen: ConcreteIndexScreen) -> None:
        item = IndexItem(id="Apple", display_text="Apple")
        button = MagicMock()
        with (
            patch.object(ConcreteIndexScreen, "_handle_expand_or_switch") as expand,
            patch.object(ConcreteIndexScreen, "_handle_item_expansion") as expansion,
        ):
            index_screen._on_index_item_press(button, item)

        expand.assert_called_once_with(button)
        expansion.assert_called_once_with(button, item)
