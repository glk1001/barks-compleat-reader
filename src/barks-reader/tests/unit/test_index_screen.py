# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import pytest
from barks_reader.core.random_title_images import ImageInfo
from barks_reader.ui.index_screen import (
    SAVED_NODE_STATE_FIRST_LETTER_KEY,
    IndexItemButton,
    IndexMenuButton,
    IndexScreen,
)
from barks_reader.ui.reader_ui_classes import MainTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Generator


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

    @staticmethod
    def _get_no_items_button(letter: str) -> IndexItemButton:
        # Return a mock instead of a real widget
        btn = MagicMock(spec=IndexItemButton)
        btn.text = f"*** No index items for '{letter}' ***"
        return btn

    def _cancel_index_image_change_events(self) -> None:
        pass

    def _get_items_for_letter(self, first_letter: str) -> list[str]:
        if first_letter == "A":
            return ["Apple", "Ant"]
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
        screen.ids.alphabet_layout = MagicMock()
        screen.ids.left_column_layout = MagicMock()
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
        # noinspection PyProtectedMember
        index_screen._populate_alphabet_menu()

        # Check if buttons were added to alphabet_layout
        # 0 + ' + A-Z = 28 buttons
        assert index_screen.ids.alphabet_layout.add_widget.call_count == 28  # noqa: PLR2004
        assert "A" in index_screen._alphabet_buttons
        assert "Z" in index_screen._alphabet_buttons
        assert "0" in index_screen._alphabet_buttons
        assert "'" in index_screen._alphabet_buttons

    def test_on_letter_press(self, index_screen: ConcreteIndexScreen) -> None:
        # noinspection PyProtectedMember
        index_screen._populate_alphabet_menu()
        button_a = index_screen._alphabet_buttons["A"]

        with patch.object(index_screen, "_populate_index_for_letter") as mock_populate:
            index_screen.on_letter_press(button_a)

            assert (
                index_screen.treeview_index_node.saved_state[SAVED_NODE_STATE_FIRST_LETTER_KEY]
                == "A"
            )
            assert button_a.is_selected is True
            # noinspection PyProtectedMember
            assert index_screen._selected_letter_button == button_a
            mock_populate.assert_called_with("A")

    def test_populate_index_grid(self, index_screen: ConcreteIndexScreen) -> None:
        # Setup
        index_screen.ids.left_column_layout.clear_widgets = MagicMock()
        index_screen.ids.right_column_layout.clear_widgets = MagicMock()

        # Test with items (Letter A returns ["Apple", "Ant"])
        # noinspection PyProtectedMember
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

        # noinspection PyProtectedMember
        index_screen._populate_index_grid("Z")  # Returns []

        # Should add "No items" button to left column
        assert index_screen.ids.left_column_layout.add_widget.call_count == 1
        # Check text of added widget
        args, _ = index_screen.ids.left_column_layout.add_widget.call_args
        assert "*** No index items for 'Z' ***" in args[0].text

    def test_on_is_visible_true(self, index_screen: ConcreteIndexScreen) -> None:
        # noinspection PyProtectedMember
        index_screen._populate_alphabet_menu()

        # Case 1: No selected button, no saved state -> Default 'A'
        with patch.object(index_screen, "on_letter_press") as mock_press:
            index_screen.on_is_visible(index_screen, value=True)
            mock_press.assert_called_with(index_screen._alphabet_buttons["A"])

        # Case 2: Saved state exists
        index_screen.treeview_index_node.saved_state[SAVED_NODE_STATE_FIRST_LETTER_KEY] = "B"
        with patch.object(index_screen, "on_letter_press") as mock_press:
            index_screen.on_is_visible(index_screen, value=True)
            mock_press.assert_called_with(index_screen._alphabet_buttons["B"])

        # Case 3: Already selected button
        # noinspection PyProtectedMember
        index_screen._selected_letter_button = index_screen._alphabet_buttons["C"]
        with patch.object(index_screen, "_new_index_image") as mock_new_image:
            index_screen.on_is_visible(index_screen, value=True)
            mock_new_image.assert_called_once()

    def test_on_is_visible_false(self, index_screen: ConcreteIndexScreen) -> None:
        with patch.object(index_screen, "_cancel_index_image_change_events") as mock_cancel:
            index_screen.on_is_visible(index_screen, value=False)
            mock_cancel.assert_called_once()

    def test_get_sortable_string(self, index_screen: ConcreteIndexScreen) -> None:
        # noinspection PyProtectedMember
        assert index_screen._get_sortable_string("The Apple") == "Apple, The"
        # noinspection PyProtectedMember
        assert index_screen._get_sortable_string("A Banana") == "Banana, A"
        # noinspection PyProtectedMember
        assert index_screen._get_sortable_string("Carrot") == "Carrot"

    def test_on_goto_background_title(self, index_screen: ConcreteIndexScreen) -> None:
        mock_func = MagicMock()
        index_screen.on_goto_background_title_func = mock_func

        # No image info
        # noinspection PyProtectedMember
        index_screen._current_image_info = None
        index_screen.on_goto_background_title()
        mock_func.assert_not_called()

        # With image info
        info = ImageInfo()
        # noinspection PyProtectedMember
        index_screen._current_image_info = info
        index_screen.on_goto_background_title()
        mock_func.assert_called_with(info)
