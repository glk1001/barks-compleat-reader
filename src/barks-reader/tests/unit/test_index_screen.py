# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.whoosh_search_engine import PageInfo, SpeechInfo
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.reader_palette import color_to_markup_hex, theme
from barks_reader.core.user_error_types import ErrorTypes, TitleNotInFantaInfoError
from barks_reader.ui.index_screen import (
    KEY_DOWN,
    SAVED_NODE_STATE_FIRST_LETTER_KEY,
    SPEECH_HIGHLIGHT_END_TAG,
    IndexItem,
    IndexItemButton,
    IndexMenuButton,
    IndexScreen,
    PopupKeyboardNav,
    TextBoxWithTitleAndBorder,
    _speech_highlight_start_tag,
    format_page_speech_bubbles,
    show_speech_bubbles_popup,
)
from barks_reader.ui.tree_view_nodes import MainTreeViewNode
from kivy.clock import Clock

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

    def test_an_expansion_moves_the_focus_once_its_sub_items_are_in(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        """However late the frame that adds them: a fixed delay once ran before it."""
        parent = MagicMock(spec=IndexItemButton)
        sub_item = MagicMock(spec=IndexItemButton)
        column = [parent, MagicMock(spec=IndexItemButton)]
        parent.trigger_action.side_effect = lambda **_kw: index_screen._schedule_sub_items(
            lambda _dt: column.insert(1, sub_item)
        )
        index_screen._nav_active = True
        index_screen._nav_panel = barks_reader.ui.index_screen._IndexNavPanel.ITEMS
        index_screen._nav_focused_col = 0
        index_screen._nav_focused_item_idx = 0

        with (
            patch.object(index_screen, "_get_col_buttons", side_effect=lambda _col: column),
            patch.object(Clock, "schedule_once") as schedule,
        ):
            index_screen._activate_focused_item()
            assert index_screen._nav_focused_item_idx == 0  # nothing to move to yet

            add_sub_items = schedule.call_args.args[0]
            add_sub_items(0.2)

        assert index_screen._nav_focused_item_idx == 1  # the first sub-item
        assert index_screen._pending_focus_resync is None

    def test_a_collapse_resyncs_the_focus_at_once(self, index_screen: ConcreteIndexScreen) -> None:
        btn_a = MagicMock(spec=IndexItemButton)
        btn_b = MagicMock(spec=IndexItemButton)
        index_screen._nav_active = True
        index_screen._nav_panel = barks_reader.ui.index_screen._IndexNavPanel.ITEMS
        index_screen._nav_focused_col = 0
        index_screen._nav_focused_item_idx = 0

        with (
            patch.object(index_screen, "_get_col_buttons", return_value=[btn_a, btn_b]),
            patch.object(Clock, "schedule_once") as schedule,
        ):
            index_screen._activate_focused_item()

        schedule.assert_not_called()
        btn_a.trigger_action.assert_called_once_with(duration=0)
        assert index_screen._nav_focused_item_idx == 0

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


def _speech(text: str, speaker: str | None = None, group_id: str = "0") -> SpeechInfo:
    return SpeechInfo(
        group_id=group_id,
        panel_num=1,
        speech_text=text,
        speech_text_markup=text,
        speaker=speaker,
    )


def _label(name: str) -> str:
    """Return the speaker line as rendered: bold italic in the speaker colour."""
    return f"[b][i][color={color_to_markup_hex(theme().speech_speaker)}]{name}:[/color][/i][/b]"


class TestFormatPageSpeechBubbles:
    """Each bubble names its speaker on a bold italic, coloured line above the lettering."""

    def test_speaker_line_above_the_bubble(self) -> None:
        page = PageInfo("5", [_speech("MONEY! MONEY!", speaker="Scrooge")])

        assert format_page_speech_bubbles(page, "zzz") == f"{_label('Scrooge')}\nMONEY! MONEY!"

    def test_speaker_line_takes_the_given_size(self) -> None:
        page = PageInfo("5", [_speech("HI", speaker="Scrooge")])

        text = format_page_speech_bubbles(page, "zzz", speaker_font_size=16)

        assert text == f"[size=16]{_label('Scrooge')}[/size][size=27] [/size]\nHI"

    def test_speaker_line_is_set_apart_by_more_than_bold(self) -> None:
        """The lettering carries [b] for emphasis, so the label must carry italic and colour too."""
        page = PageInfo("5", [_speech("A [b]BIG[/b] DEAL", speaker="Scrooge")])

        text = format_page_speech_bubbles(page, "zzz")

        assert text.startswith("[b][i][color=")
        assert text.endswith("[/color][/i][/b]\nA [b]BIG[/b] DEAL")

    def test_bubbles_are_separated_by_a_blank_line(self) -> None:
        page = PageInfo(
            "5",
            [_speech("ONE", speaker="Donald", group_id="0"), _speech("TWO", speaker="nephews")],
        )

        assert format_page_speech_bubbles(page, "zzz") == (
            f"{_label('Donald')}\nONE\n\n{_label('Nephews')}\nTWO"
        )

    def test_no_speaker_call_renders_as_before(self) -> None:
        """An index built before speakers existed shows plain bubbles."""
        page = PageInfo("5", [_speech("ONE"), _speech("TWO", group_id="1")])

        assert format_page_speech_bubbles(page, "zzz") == "ONE\n\nTWO"

    def test_none_speaker_gets_no_line(self) -> None:
        """A sound effect or a sign is nobody's line."""
        page = PageInfo("5", [_speech("CRASH!", speaker="none")])

        assert format_page_speech_bubbles(page, "zzz") == "CRASH!"

    def test_sentinels_and_other_names(self) -> None:
        page = PageInfo(
            "5",
            [
                _speech("LATER...", speaker="narrator", group_id="0"),
                _speech("HEE HEE!", speaker="other:Witch Hazel", group_id="1"),
                _speech("WHO?", speaker="unknown", group_id="2"),
            ],
        )

        assert format_page_speech_bubbles(page, "zzz") == (
            f"{_label('Narrator')}\nLATER...\n\n{_label('Witch Hazel')}\nHEE HEE!"
            f"\n\n{_label('Unknown')}\nWHO?"
        )

    def test_label_is_escaped_for_markup(self) -> None:
        page = PageInfo("5", [_speech("HI", speaker="other:Goldstein & Co.")])

        assert format_page_speech_bubbles(page, "zzz") == f"{_label('Goldstein &amp; Co.')}\nHI"

    def test_search_term_highlighted_in_the_lettering_not_the_label(self) -> None:
        page = PageInfo("5", [_speech("OH, DONALD!", speaker="Donald")])

        text = format_page_speech_bubbles(page, "donald")

        start = _speech_highlight_start_tag()
        assert text == f"{_label('Donald')}\nOH, {start}DONALD{SPEECH_HIGHLIGHT_END_TAG}!"

    def test_the_query_terms_are_highlighted_instead_of_the_search_text(self) -> None:
        page = PageInfo("5", [_speech("DUCKS DUCKING GOLD", speaker="Donald")])

        text = format_page_speech_bubbles(page, "duck -gold", highlight_terms=["ducks", "ducking"])

        start, end = _speech_highlight_start_tag(), SPEECH_HIGHLIGHT_END_TAG
        assert text == f"{_label('Donald')}\n{start}DUCKS{end} {start}DUCKING{end} GOLD"

    def test_soft_hyphens_become_hyphens(self) -> None:
        page = PageInfo("5", [_speech("SUPER\u00adDUCK", speaker="Donald")])

        assert format_page_speech_bubbles(page, "zzz") == f"{_label('Donald')}\nSUPER-DUCK"


class TestPopupKeyboardNavWindowBinding:
    """The speech-bubble popup owns the keyboard via its own Window binding.

    The main screen yields to the modal popup (see `_modal_popup_is_open`), so the
    nav helper must bind `Window.on_key_down` itself to receive keys while open.
    """

    @staticmethod
    def _make_nav() -> PopupKeyboardNav:
        return PopupKeyboardNav(MagicMock())

    def test_on_opened_binds_window_key_handler(self, loguru_sink: list[str]) -> None:
        nav = self._make_nav()
        with (
            patch.object(barks_reader.ui.index_screen, "Window") as window,
            patch.object(barks_reader.ui.index_screen, "Clock"),
        ):
            nav._on_opened()

        window.bind.assert_called_once_with(on_key_down=nav._on_key_down)
        assert "Speech bubbles popup opened." in loguru_sink

    def test_on_dismissed_unbinds_window_key_handler(self, loguru_sink: list[str]) -> None:
        nav = self._make_nav()
        with (
            patch.object(barks_reader.ui.index_screen, "Window") as window,
            patch.object(PopupKeyboardNav, "_clear_focus"),
        ):
            nav._on_dismissed()

        window.unbind.assert_called_once_with(on_key_down=nav._on_key_down)
        assert "Speech bubbles popup dismissed." in loguru_sink

    def test_drawing_the_focus_logs_the_entry_it_landed_on(self, loguru_sink: list[str]) -> None:
        """The ring inside the popup logs like every other, so a test can step it."""
        nav = self._make_nav()
        entry = MagicMock()
        entry.text = "a bubble"
        with (
            patch.object(PopupKeyboardNav, "_get_entries", return_value=[entry]),
            patch.object(barks_reader.ui.index_screen, "Color"),
            patch.object(barks_reader.ui.index_screen, "Line"),
        ):
            nav._draw_focus()
        assert any(line.startswith("Nav focus on") for line in loguru_sink)

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


class TestIndexScreenMarkers:
    def test_an_empty_letter_logs_no_items(
        self, index_screen: ConcreteIndexScreen, loguru_sink: list[str]
    ) -> None:
        """The populated line fires for a letter with items; an empty letter says so instead."""
        index_screen._populate_index_grid("B")
        assert "Populated index page for letter 'B': no items." in loguru_sink


class TestEnterNavFocusMarker:
    def test_entering_nav_focus_logs_once_the_focus_is_drawn(
        self, index_screen: ConcreteIndexScreen, loguru_sink: list[str]
    ) -> None:
        index_screen._selected_letter_button = None
        with patch.object(ConcreteIndexScreen, "_draw_letter_focus") as draw:
            index_screen.enter_nav_focus(lambda: None)
        draw.assert_called_once()
        assert loguru_sink[-1] == "IndexScreen: entered nav focus."

    def test_a_restored_item_focus_logs_too(
        self, index_screen: ConcreteIndexScreen, loguru_sink: list[str]
    ) -> None:
        with (
            patch.object(ConcreteIndexScreen, "_restore_item_focus", return_value=True),
            patch.object(ConcreteIndexScreen, "_draw_letter_focus") as draw,
        ):
            index_screen.enter_nav_focus(lambda: None)
        draw.assert_not_called()
        assert "IndexScreen: entered nav focus." in loguru_sink


# ---------------------------------------------------------------------------
# The remote's keys inside the speech-bubble popup, and in the items panel:
# the paths no GUI test walks.
# ---------------------------------------------------------------------------

_module = barks_reader.ui.index_screen


class _StubbedPopupNav(PopupKeyboardNav):
    """The popup's navigator over stand-in bubbles, its drawing recorded rather than done."""

    def __init__(self, entries: list[MagicMock]) -> None:
        super().__init__(MagicMock())
        self.entries = entries
        self.drawn = MagicMock()
        self.cleared = MagicMock()

    def _get_entries(self) -> list[TextBoxWithTitleAndBorder]:
        return cast("list[TextBoxWithTitleAndBorder]", self.entries)

    def _draw_focus(self) -> None:
        self.drawn()

    def _clear_focus(self) -> None:
        self.cleared()


def _popup_nav(entries: list[MagicMock]) -> tuple[_StubbedPopupNav, MagicMock, MagicMock]:
    nav = _StubbedPopupNav(entries)
    return nav, nav.drawn, nav.cleared


class TestPopupKeyboardNavKeys:
    def test_down_and_up_step_through_the_bubbles(self) -> None:
        nav, drawn, _ = _popup_nav([MagicMock(), MagicMock(), MagicMock()])
        assert nav.handle_key(_module.KEY_DOWN) is True
        assert nav.handle_key(_module.KEY_DOWN) is True
        assert nav._focused_idx == 2
        assert nav.handle_key(_module.KEY_UP) is True
        assert nav._focused_idx == 1
        assert drawn.call_count == 3

    def test_the_focus_stops_at_either_end(self) -> None:
        nav, drawn, cleared = _popup_nav([MagicMock(), MagicMock()])
        nav.handle_key(_module.KEY_UP)  # already at the first
        nav._focused_idx = 1
        nav.handle_key(_module.KEY_DOWN)  # already at the last
        assert nav._focused_idx == 1
        drawn.assert_not_called()
        cleared.assert_not_called()

    def test_with_no_bubbles_nothing_moves(self) -> None:
        nav, drawn, _ = _popup_nav([])
        nav.handle_key(_module.KEY_DOWN)
        assert nav._focused_idx == 0
        drawn.assert_not_called()

    def test_page_keys_scroll_the_bubbles_within_bounds(self) -> None:
        nav, _, _ = _popup_nav([])
        content = MagicMock(spec=_module.ScrollView)
        content.scroll_y = 0.5
        nav._popup.content = content
        assert nav.handle_key(_module.KEY_PAGE_DOWN) is True
        assert content.scroll_y < 0.5
        content.scroll_y = 0.95
        nav.handle_key(_module.KEY_PAGE_UP)
        assert content.scroll_y == 1.0

    def test_with_no_bubbles_no_focus_is_drawn(self, loguru_sink: list[str]) -> None:
        nav = PopupKeyboardNav(MagicMock())
        nav._popup.content = None
        nav._draw_focus()
        assert nav._focused_idx == 0
        assert not any(line.startswith("Nav focus on") for line in loguru_sink)

    def test_another_key_is_not_the_popups(self) -> None:
        nav, _, _ = _popup_nav([])
        assert nav.handle_key(_module.KEY_LEFT) is False

    def test_the_bubbles_are_the_grids_children_in_display_order(self) -> None:
        nav = PopupKeyboardNav(MagicMock())
        nav._popup.content = None
        assert nav._get_entries() == []
        first, second = MagicMock(), MagicMock()
        grid = MagicMock()
        grid.children = [second, first]  # Kivy keeps the last added first
        nav._popup.content = MagicMock(children=[grid])
        assert nav._get_entries() == [first, second]


@pytest.fixture
def items_nav(index_screen: ConcreteIndexScreen) -> Generator[tuple[ConcreteIndexScreen, dict]]:
    """Put the items panel in nav mode, over stand-in columns each test fills."""
    columns: dict[int, list[MagicMock]] = {0: [], 1: []}
    index_screen._nav_active = True
    index_screen._nav_panel = _module._IndexNavPanel.ITEMS
    index_screen._nav_focused_col = 0
    index_screen._nav_focused_item_idx = 0
    with (
        patch.object(index_screen, "_get_col_buttons", side_effect=lambda col: columns[col]),
        patch.object(_module, "draw_focus_highlight"),
        patch.object(_module, "clear_focus_in_list"),
    ):
        yield index_screen, columns


class TestItemsPanelKeys:
    def test_a_screen_out_of_nav_mode_takes_no_key(self, index_screen: ConcreteIndexScreen) -> None:
        index_screen._nav_active = False
        assert index_screen.handle_key(_module.KEY_DOWN) is False

    def test_page_keys_scroll_the_index(self, items_nav: tuple[ConcreteIndexScreen, dict]) -> None:
        screen, _ = items_nav
        screen.ids.index_scroll_view.scroll_y = 0.5
        assert screen.handle_key(_module.KEY_PAGE_DOWN) is True
        assert screen.ids.index_scroll_view.scroll_y < 0.5
        screen.ids.index_scroll_view.scroll_y = 0.05
        screen.handle_key(_module.KEY_PAGE_DOWN)
        assert screen.ids.index_scroll_view.scroll_y == 0.0
        screen.handle_key(_module.KEY_PAGE_UP)
        assert screen.ids.index_scroll_view.scroll_y > 0.0

    def test_another_key_is_not_the_panels(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, _ = items_nav
        assert screen.handle_key(_module.KEY_PAGE_DOWN + 1000) is False

    def test_down_past_a_columns_last_item_goes_to_the_next_columns_first(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0], columns[1] = [MagicMock(), MagicMock()], [MagicMock()]
        screen._nav_focused_item_idx = 1
        screen.handle_key(_module.KEY_DOWN)
        assert (screen._nav_focused_col, screen._nav_focused_item_idx) == (1, 0)

    def test_up_from_a_columns_first_item_goes_to_the_previous_columns_last(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0], columns[1] = [MagicMock(), MagicMock(), MagicMock()], [MagicMock()]
        screen._nav_focused_col = 1
        screen.handle_key(_module.KEY_UP)
        assert (screen._nav_focused_col, screen._nav_focused_item_idx) == (0, 2)

    def test_up_from_a_later_item_goes_to_the_one_above(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0] = [MagicMock(), MagicMock(), MagicMock()]
        screen._nav_focused_item_idx = 2
        screen.handle_key(_module.KEY_UP)
        assert (screen._nav_focused_col, screen._nav_focused_item_idx) == (0, 1)
        assert screen._nav_focused_btn is columns[0][1]

    def test_up_from_the_very_first_item_stays(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0] = [MagicMock()]
        screen.handle_key(_module.KEY_UP)
        assert (screen._nav_focused_col, screen._nav_focused_item_idx) == (0, 0)

    def test_right_into_an_empty_column_or_past_the_last_stays(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0] = [MagicMock()]
        screen.handle_key(_module.KEY_RIGHT)  # column 1 is empty
        assert screen._nav_focused_col == 0
        columns[1] = [MagicMock()]
        screen._nav_focused_col = 1
        screen.handle_key(_module.KEY_RIGHT)  # no column 2
        assert screen._nav_focused_col == 1

    def test_keys_in_an_empty_column_do_nothing(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, _ = items_nav
        screen.handle_key(_module.KEY_DOWN)
        screen.handle_key(_module.KEY_ENTER)
        assert (screen._nav_focused_col, screen._nav_focused_item_idx) == (0, 0)

    def test_right_from_the_letters_needs_items_to_go_to(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, _ = items_nav
        screen._nav_panel = _module._IndexNavPanel.ALPHABET
        screen._enter_items_panel()
        assert screen._nav_panel is _module._IndexNavPanel.ALPHABET

    def test_a_resync_out_of_the_items_panel_does_nothing(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0] = [MagicMock(), MagicMock()]
        screen._nav_panel = _module._IndexNavPanel.ALPHABET
        screen._nav_focused_item_idx = 1
        screen._resync_item_focus(MagicMock(), 1)
        assert screen._nav_focused_item_idx == 1

    def test_a_resync_whose_button_has_gone_stays_near_where_it_was(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        columns[0] = [MagicMock(), MagicMock()]
        screen._nav_focused_item_idx = 5
        screen._resync_item_focus(MagicMock(), 3)  # not in the column any more
        assert screen._nav_focused_item_idx == 1

    def test_an_item_whose_action_empties_its_column_leaves_no_focus_to_draw(
        self, items_nav: tuple[ConcreteIndexScreen, dict]
    ) -> None:
        screen, columns = items_nav
        only_item = MagicMock()
        columns[0] = [only_item]
        only_item.trigger_action.side_effect = lambda **_kw: columns[0].clear()

        screen.handle_key(_module.KEY_ENTER)

        only_item.trigger_action.assert_called_once_with(duration=0)
        assert screen._nav_focused_item_idx == 0
        assert screen._nav_focused_btn is None
        screen.ids.index_scroll_view.scroll_to.assert_not_called()

    def test_a_saved_item_focus_whose_button_has_gone_falls_back_to_the_letters(
        self, items_nav: tuple[ConcreteIndexScreen, dict], loguru_sink: list[str]
    ) -> None:
        """The grid is unchanged by its version, but the button is in no column."""
        screen, columns = items_nav
        columns[0], columns[1] = [MagicMock()], [MagicMock()]
        screen._nav_saved_grid_version = screen._grid_version
        screen._nav_focused_btn = MagicMock()
        with patch.object(ConcreteIndexScreen, "_draw_letter_focus") as draw_letter:
            screen.enter_nav_focus(lambda: None)
        draw_letter.assert_called_once()
        assert screen._nav_panel is _module._IndexNavPanel.ALPHABET
        assert "IndexScreen: entered nav focus." in loguru_sink


class TestShowSpeechBubblesPopup:
    @pytest.fixture
    def popup(self) -> Generator[MagicMock]:
        """Fill a stand-in popup, the widgets it is built from stood in for too."""
        with (
            patch.object(_module, "GridLayout"),
            patch.object(_module, "TextBoxWithTitleAndBorder"),
            patch.object(_module, "ReaderScrollView") as scroll_view_cls,
        ):
            popup = MagicMock()
            popup.scroll_view = scroll_view_cls.return_value
            yield popup

    def test_a_speaker_filter_is_named_in_the_title(self, popup: MagicMock) -> None:
        show_speech_bubbles_popup(
            popup,
            "Lost in the Andes!",
            "square eggs",
            MagicMock(fanta_pages={}),
            MagicMock(),
            title_font_size=20,
            speaker="other:Goldstein & Co.",
        )

        assert popup.title == (
            "[b][i]Lost in the Andes!  —  [/i]'square eggs'[/b][b]  —  [/b]Goldstein &amp; Co."
        )
        assert popup.content is popup.scroll_view
        popup.open.assert_called_once()

    def test_without_a_speaker_the_title_is_the_story_and_the_search(
        self, popup: MagicMock
    ) -> None:
        show_speech_bubbles_popup(
            popup, "Lost in the Andes!", "eggs", MagicMock(fanta_pages={}), MagicMock(), 20
        )
        assert popup.title == "[b][i]Lost in the Andes!  —  [/i]'eggs'[/b]"


class TestSetBackgroundImage:
    @staticmethod
    def _load_andes(screen: ConcreteIndexScreen) -> tuple[ImageInfo, Any]:
        """Set the Andes panel as the background; return it and the loader's ready callback."""
        loader = MagicMock()
        screen._texture_loader = loader
        info = ImageInfo(from_title=Titles.LOST_IN_THE_ANDES, filename=Path("andes.png"))
        screen._set_background_image(info)
        filename, on_ready = loader.load_texture.call_args.args
        assert filename == Path("andes.png")
        return info, on_ready

    def test_a_failed_load_is_raised(self, index_screen: ConcreteIndexScreen) -> None:
        _info, on_ready = self._load_andes(index_screen)

        with pytest.raises(RuntimeError, match="no such panel"):
            on_ready(None, FileNotFoundError("no such panel"))

    def test_a_loaded_texture_becomes_the_background(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        info, on_ready = self._load_andes(index_screen)
        texture = MagicMock()

        on_ready(texture, None)

        assert index_screen.image_texture is texture
        assert index_screen._current_image_info is info
        assert index_screen.current_title_str == ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]

    def test_an_image_with_no_file_clears_the_background(
        self, index_screen: ConcreteIndexScreen
    ) -> None:
        _info, on_ready = self._load_andes(index_screen)
        on_ready(MagicMock(), None)
        loader = MagicMock()
        index_screen._texture_loader = loader

        index_screen._set_background_image(ImageInfo(from_title=Titles.LOST_IN_THE_ANDES))

        assert index_screen.image_texture is None
        loader.load_texture.assert_not_called()
        assert index_screen.current_title_str == ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]


def test_a_title_whose_volume_is_missing_is_reported(index_screen: ConcreteIndexScreen) -> None:
    item = IndexItem(id=Titles.LOST_IN_THE_ANDES, display_text="Lost in the Andes!")
    index_screen.on_goto_title = MagicMock(side_effect=TitleNotInFantaInfoError("Andes"))
    index_screen._user_error_handler = MagicMock()
    with patch.object(_module.Clock, "schedule_once", side_effect=lambda f, _t: f(0)):
        index_screen._handle_title(MagicMock(), item)
    error_type, _info = index_screen._user_error_handler.handle_error.call_args.args
    assert error_type is ErrorTypes.ArchiveVolumeNotAvailable
