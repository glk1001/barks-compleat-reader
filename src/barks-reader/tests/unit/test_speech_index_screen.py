# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.speech_index_screen
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import ImageInfo
from barks_reader.ui.index_screen import (
    IndexItem,
    TitleShowSpeechButton,
    _IndexNavPanel,
)
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_RIGHT,
    KEY_UP,
)
from barks_reader.ui.speech_index_screen import (
    SpeechIndexScreen,
    _SpeechIndexTitleItemButton,
)
from kivy.clock import Clock

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.file_paths.barks_panels_are_encrypted = False
    settings.sys_file_paths.get_barks_reader_indexes_dir.return_value = "indexes_dir"
    return settings


@pytest.fixture
def speech_index_screen(
    mock_settings: MagicMock,
    mock_font_manager: MagicMock,
    mock_user_error_handler: MagicMock,
) -> Generator[SpeechIndexScreen]:
    # Patch IndexScreen.__init__ to avoid Kivy widget initialization
    with patch.object(barks_reader.ui.index_screen.IndexScreen, "__init__"):  # noqa: SIM117
        with (
            patch.object(barks_reader.ui.speech_index_screen, "ComicSearch") as mock_search_cls,
            patch.object(barks_reader.ui.speech_index_screen, "ImageSelector") as mock_random_cls,
            patch.object(barks_reader.ui.speech_index_screen, "ReaderFilePathsResolver"),
            patch.object(
                barks_reader.ui.speech_index_screen, "PanelTextureLoader"
            ) as mock_loader_cls,
            patch.object(
                barks_reader.ui.speech_index_screen,
                "create_speech_bubble_popup",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch.object(SpeechIndexScreen, "_populate_alphabet_menu"),
        ):
            # Setup mock search engine
            mock_indexer = mock_search_cls.return_value
            # Required structure: {letter: {prefix: [terms]}}
            mock_indexer.get_alpha_split_terms.return_value = {
                "a": {"apple": ["apple", "apples"], "ant": ["ant"]},
                "b": {"banana": ["banana"]},
            }

            screen = SpeechIndexScreen(mock_settings, mock_font_manager, mock_user_error_handler)

            # Manual init of attributes skipped by patching IndexScreen.__init__
            screen.ids = MagicMock()
            screen.ids.alphabet_top_split_layout = MagicMock()
            screen.ids.left_column_layout = MagicMock()
            screen.ids.right_column_layout = MagicMock()
            screen.ids.index_scroll_view = MagicMock()

            screen.index_theme = MagicMock()
            screen._font_manager = mock_font_manager
            screen._random_title_images = mock_random_cls.return_value
            screen._texture_loader = mock_loader_cls.return_value
            screen._search = mock_indexer

            screen.treeview_index_node = MagicMock()
            screen.treeview_index_node.saved_state = {}
            screen._alphabet_buttons = {}
            screen.on_after_popup_goto_title = None

            yield screen


class TestSpeechIndexScreen:
    def test_init(self, speech_index_screen: SpeechIndexScreen) -> None:
        assert speech_index_screen._search is not None
        assert speech_index_screen._cleaned_alpha_split_terms is not None

    def test_populate_top_alphabet_split_menu(self, speech_index_screen: SpeechIndexScreen) -> None:
        # Mock IndexPrefixButton
        with patch.object(barks_reader.ui.speech_index_screen, "IndexPrefixButton") as mock_btn_cls:
            mock_btn = MagicMock()
            mock_btn.text = "apple"
            mock_btn_cls.return_value = mock_btn

            # Mock _populate_index_grid to prevent further chain execution
            with patch.object(speech_index_screen, "_populate_index_grid"):
                speech_index_screen._populate_top_alphabet_split_menu("A")

                # Should create buttons for "apple" and "ant"
                assert mock_btn_cls.call_count == 2  # noqa: PLR2004
                assert (
                    speech_index_screen.ids.alphabet_top_split_layout.add_widget.call_count == 2  # noqa: PLR2004
                )

    def test_on_letter_prefix_press(self, speech_index_screen: SpeechIndexScreen) -> None:
        # Setup
        mock_button = MagicMock()
        mock_button.text = "ant"

        # Mock _populate_index_grid to verify it's called
        with patch.object(speech_index_screen, "_populate_index_grid") as mock_populate_grid:
            speech_index_screen.on_letter_prefix_press(mock_button)

            assert speech_index_screen.treeview_index_node is not None
            assert speech_index_screen.treeview_index_node.saved_state["prefix"] == "ant"
            assert speech_index_screen._selected_prefix_button == mock_button

            # Check items populated for "A" (from "ant" prefix)
            items = speech_index_screen._item_index["A"]
            assert len(items) == 1
            assert items[0].display_text == "ant"

            mock_populate_grid.assert_called_with("A")

    def test_populate_index_for_letter_builds_the_grid_exactly_once(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        """Selecting a prefix already populates the grid.

        A second call from _populate_index_for_letter would rebuild every widget and
        kick off a second background-image load that cancels the first.
        """
        with (
            patch.object(barks_reader.ui.speech_index_screen, "IndexPrefixButton") as mock_btn_cls,
            patch.object(speech_index_screen, "_populate_index_grid") as mock_populate_grid,
        ):
            mock_btn_cls.side_effect = lambda text: MagicMock(text=text)

            speech_index_screen._populate_index_for_letter("A")

            mock_populate_grid.assert_called_once_with("A")

    def test_populate_top_alphabet_split_menu_clears_stale_prefix_buttons(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        """Prefix buttons from a previously visited letter must not be retained."""
        with (
            patch.object(barks_reader.ui.speech_index_screen, "IndexPrefixButton") as mock_btn_cls,
            patch.object(speech_index_screen, "_populate_index_grid"),
        ):
            mock_btn_cls.side_effect = lambda text: MagicMock(text=text)

            speech_index_screen._populate_top_alphabet_split_menu("A")
            assert set(speech_index_screen._prefix_buttons) == {"apple", "ant"}

            speech_index_screen._populate_top_alphabet_split_menu("B")
            assert set(speech_index_screen._prefix_buttons) == {"banana"}

    def test_find_words(self, speech_index_screen: SpeechIndexScreen) -> None:
        speech_index_screen._find_words("test")
        speech_index_screen._search.find_words.assert_called_with("test")

        speech_index_screen._find_words("1942")
        speech_index_screen._search.find_words.assert_called_with("1942")

    def test_next_background_image(self, speech_index_screen: SpeechIndexScreen) -> None:
        # Setup state
        mock_selected_letter = MagicMock()
        mock_selected_letter.text = "A"
        speech_index_screen._selected_letter_button = mock_selected_letter

        # Populate item index
        speech_index_screen._item_index["A"] = [IndexItem("term", "term")]

        # Mock find_words
        with patch.object(  # noqa: SIM117
            speech_index_screen, "_find_words", return_value={"Title": MagicMock()}
        ):
            # Mock the title-string -> Titles enum -> FantaComicBookInfo lookup chain.
            with (
                patch.object(barks_reader.ui.speech_index_screen, "STR_TITLE_TO_ENUM"),
                patch.object(
                    barks_reader.ui.speech_index_screen, "ALL_FANTA_COMIC_BOOK_INFO"
                ) as mock_all_info,
            ):
                mock_info = MagicMock()
                mock_all_info.__getitem__.return_value = mock_info

                # Mock random image
                image_info = ImageInfo(
                    filename=Path("img.png"), from_title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
                )
                speech_index_screen._random_title_images.get_random_image.return_value = image_info

                # Execute
                speech_index_screen._next_background_image()

                # Verify
                cast("MagicMock", speech_index_screen._texture_loader).load_texture.assert_called()
                assert speech_index_screen.current_title_str != ""

    def test_handle_title_from_bubble_press(self, speech_index_screen: SpeechIndexScreen) -> None:
        mock_callback = MagicMock()
        mock_after_goto = MagicMock()
        speech_index_screen.on_goto_title = mock_callback
        speech_index_screen.on_after_popup_goto_title = mock_after_goto

        with patch.object(Clock, "schedule_once") as mock_schedule:
            speech_index_screen._handle_title_from_bubble_press(
                "Donald Duck Finds Pirate Gold", "5"
            )

            speech_index_screen._speech_bubble_browser_popup.dismiss.assert_called_once()

            # Execute lambda
            args, _ = mock_schedule.call_args
            args[0](0)

            mock_callback.assert_called()
            # The popup goto must also request the title-portal focus hand-off.
            mock_after_goto.assert_called_once()


class TestSpeechButtonKeyboardNav:
    """The speech button is a sub-panel of a title row, reached with Right."""

    @staticmethod
    def _title_row(screen: SpeechIndexScreen) -> tuple[MagicMock, MagicMock]:
        """Build a title button paired with its speech button, as the grid lays them out."""
        title_btn = MagicMock(spec=_SpeechIndexTitleItemButton)
        speech_btn = MagicMock(spec=TitleShowSpeechButton)
        parent = MagicMock()
        # Kivy's children list runs bottom-to-top, so the speech button sits at
        # the index just below its title button.
        parent.children = [speech_btn, title_btn]
        title_btn.parent = parent
        screen._nav_focused_col = 0
        screen._nav_focused_item_idx = 0
        return title_btn, speech_btn

    def test_pairs_a_title_button_with_its_speech_button(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        title_btn, speech_btn = self._title_row(speech_index_screen)

        assert speech_index_screen._get_paired_speech_button(title_btn) is speech_btn

    def test_a_plain_button_has_no_paired_speech_button(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        assert speech_index_screen._get_paired_speech_button(MagicMock()) is None

    def test_orphan_title_button_has_no_paired_speech_button(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        title_btn = MagicMock(spec=_SpeechIndexTitleItemButton)
        title_btn.parent = None

        assert speech_index_screen._get_paired_speech_button(title_btn) is None

    def test_speech_buttons_are_not_reachable_with_up_down(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        """Up/Down walks title rows; the speech button is entered sideways instead."""
        title_btn, speech_btn = self._title_row(speech_index_screen)
        with patch.object(
            barks_reader.ui.index_screen.IndexScreen,
            "_get_col_buttons",
            return_value=[speech_btn, title_btn],
        ):
            assert speech_index_screen._get_col_buttons(0) == [title_btn]

    def test_right_from_a_title_row_enters_the_speech_button(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        title_btn, _ = self._title_row(speech_index_screen)
        with (
            patch.object(speech_index_screen, "_get_col_buttons", return_value=[title_btn]),
            patch.object(speech_index_screen, "_clear_all_item_focus"),
            patch.object(speech_index_screen, "_draw_item_focus"),
        ):
            consumed = speech_index_screen._handle_items_key(KEY_RIGHT)

        assert consumed is True
        assert speech_index_screen._nav_on_speech_btn is True

    @pytest.mark.parametrize("key", [KEY_UP, KEY_DOWN, KEY_LEFT])
    def test_leaving_the_speech_button_returns_focus_to_its_title_row(
        self, speech_index_screen: SpeechIndexScreen, key: int
    ) -> None:
        speech_index_screen._nav_on_speech_btn = True
        with (
            patch.object(speech_index_screen, "_clear_all_item_focus"),
            patch.object(speech_index_screen, "_draw_item_focus"),
        ):
            consumed = speech_index_screen._handle_items_key(key)

        assert consumed is True
        assert speech_index_screen._nav_on_speech_btn is False

    def test_enter_on_the_speech_button_opens_the_popup(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        title_btn, speech_btn = self._title_row(speech_index_screen)
        speech_index_screen._nav_on_speech_btn = True
        with patch.object(speech_index_screen, "_get_col_buttons", return_value=[title_btn]):
            consumed = speech_index_screen._handle_items_key(KEY_ENTER)

        assert consumed is True
        speech_btn.trigger_action.assert_called_once_with(duration=0)

    def test_escape_from_the_speech_button_backs_out_to_the_prefix_bar(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen._nav_on_speech_btn = True
        with patch.object(speech_index_screen, "_on_back_from_items") as back:
            consumed = speech_index_screen._handle_items_key(KEY_ESCAPE)

        assert consumed is True
        assert speech_index_screen._nav_on_speech_btn is False
        back.assert_called_once()


class TestPrefixPanelNav:
    @staticmethod
    def _visible(screen: SpeechIndexScreen, count: int) -> list[MagicMock]:
        buttons = [MagicMock(text=f"p{n}") for n in range(count)]
        screen.ids.alphabet_top_split_layout.children = list(reversed(buttons))
        return buttons

    def test_left_from_the_first_prefix_goes_back_to_the_alphabet(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        self._visible(speech_index_screen, 3)
        speech_index_screen._nav_focused_prefix_idx = 0
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus"),
            patch.object(speech_index_screen, "_enter_alphabet_panel") as alphabet,
        ):
            assert speech_index_screen._handle_prefix_key(KEY_LEFT) is True

        alphabet.assert_called_once()

    def test_right_from_the_last_prefix_drops_into_the_items_grid(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        buttons = self._visible(speech_index_screen, 3)
        speech_index_screen._nav_focused_prefix_idx = len(buttons) - 1
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus"),
            patch.object(speech_index_screen, "_enter_items_panel") as items,
        ):
            assert speech_index_screen._handle_prefix_key(KEY_RIGHT) is True

        items.assert_called_once()

    def test_moving_along_the_bar_selects_as_it_goes(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        buttons = self._visible(speech_index_screen, 3)
        speech_index_screen._nav_focused_prefix_idx = 0
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus"),
            patch.object(speech_index_screen, "_draw_prefix_focus"),
            patch.object(speech_index_screen, "on_letter_prefix_press") as press,
        ):
            assert speech_index_screen._handle_prefix_key(KEY_RIGHT) is True

        assert speech_index_screen._nav_focused_prefix_idx == 1
        press.assert_called_once_with(buttons[1])

    def test_down_drops_into_the_items_grid(self, speech_index_screen: SpeechIndexScreen) -> None:
        self._visible(speech_index_screen, 3)
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus"),
            patch.object(speech_index_screen, "_enter_items_panel") as items,
        ):
            assert speech_index_screen._handle_prefix_key(KEY_DOWN) is True

        items.assert_called_once()

    def test_an_unhandled_key_is_not_consumed(self, speech_index_screen: SpeechIndexScreen) -> None:
        self._visible(speech_index_screen, 3)

        assert speech_index_screen._handle_prefix_key(KEY_PAGE_DOWN) is False

    def test_prefix_panel_keys_are_dispatched_from_the_panel_seam(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        """PREFIX is an added dispatch case, not an override of handle_key."""
        with patch.object(speech_index_screen, "_handle_prefix_key") as prefix_key:
            speech_index_screen._handle_panel_key(_IndexNavPanel.PREFIX, KEY_LEFT)

        prefix_key.assert_called_once_with(KEY_LEFT)
