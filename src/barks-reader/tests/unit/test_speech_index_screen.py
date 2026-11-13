# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.speech_index_screen
import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.entity_types import EntityType
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.index_items import IndexItem
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_RIGHT,
    KEY_UP,
)
from barks_reader.core.user_error_types import ErrorTypes, TitleNotInFantaInfoError
from barks_reader.ui.index_screen import (
    IndexPrefixButton,
    TitleShowSpeechButton,
    _IndexNavPanel,
)
from barks_reader.ui.speech_index_screen import (
    _SEARCH_CACHE_MAX_ENTRIES,
    SpeechIndexScreen,
    _SpeechIndexTitleItemButton,
    _store_bounded,
)
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.layout import Layout
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.gridlayout import GridLayout


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


def _mock_prefix_button(prefix: str, letter: str, text: str) -> MagicMock:
    return MagicMock(prefix=prefix, letter=letter, text=text)


# The split as the real index gives it: digits and the apostrophe have letters of
# their own, and a prefix is a range label that need not start with its letter.
_REAL_SHAPED_SPLIT = {
    "0": {"00-10": ["007", "10"], "8-99": ["8", "99"], "90-99": ["90", "99"]},
    "'": {"'2-'y": ["'em", "'twas"]},
    "a": {"a-aa": ["a", "aa"], "ab-ac": ["abandon", "ace"]},
    "b": {"b-ba": ["b", "baa"]},
}


class TestPrefixesShapedLikeTheRealOnes:
    """The fixture's prefixes ("apple", "ant") start with their letter; real ones need not."""

    @pytest.fixture
    def screen(self, speech_index_screen: SpeechIndexScreen) -> Generator[SpeechIndexScreen]:
        speech_index_screen._cleaned_alpha_split_terms = _REAL_SHAPED_SPLIT
        with (
            patch.object(_speech_module, "IndexPrefixButton", side_effect=_mock_prefix_button),
            patch.object(speech_index_screen, "_populate_index_grid"),
        ):
            yield speech_index_screen

    @pytest.mark.parametrize(
        ("letter", "prefix", "words"),
        [
            ("0", "00-10", ["007", "10"]),
            ("0", "8-99", ["8", "99"]),
            # "90-99" sorts after "9": read off the label it was not a digit prefix.
            ("0", "90-99", ["90", "99"]),
            ("'", "'2-'y", ["'em", "'twas"]),
            ("A", "ab-ac", ["abandon", "ace"]),
        ],
    )
    def test_a_prefix_shows_the_words_under_its_own_letter(
        self, screen: SpeechIndexScreen, letter: str, prefix: str, words: list[str]
    ) -> None:
        screen._populate_top_alphabet_split_menu(letter)

        screen.on_letter_prefix_press(screen._prefix_buttons[prefix])

        assert [item.id for item in screen._item_index[letter]] == words
        cast("MagicMock", screen._populate_index_grid).assert_called_with(letter)

    def test_a_prefix_button_carries_its_letter(self, screen: SpeechIndexScreen) -> None:
        screen._populate_top_alphabet_split_menu("0")
        assert {b.letter for b in screen._prefix_buttons.values()} == {"0"}

    def test_changing_letter_shows_its_first_prefix_without_a_warning(
        self, screen: SpeechIndexScreen, loguru_sink: list[str]
    ) -> None:
        """One prefix is saved for the node: every letter change found it invalid."""
        screen._populate_top_alphabet_split_menu("A")
        screen.on_letter_prefix_press(screen._prefix_buttons["ab-ac"])

        screen._populate_top_alphabet_split_menu("B")

        assert screen._selected_prefix_button is screen._prefix_buttons["b-ba"]
        assert screen.treeview_index_node is not None
        assert screen.treeview_index_node.saved_state["prefix"] == "b-ba"
        assert not any("Invalid restored prefix" in line for line in loguru_sink)

    def test_the_saved_prefix_is_restored_on_its_own_letter(
        self, screen: SpeechIndexScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.treeview_index_node is not None
        screen.treeview_index_node.saved_state["prefix"] = "ab-ac"

        screen._populate_top_alphabet_split_menu("A")

        assert screen._selected_prefix_button is screen._prefix_buttons["ab-ac"]
        assert not any("Invalid restored prefix" in line for line in loguru_sink)

    def test_a_saved_prefix_the_restored_letter_does_not_have_is_logged(
        self, screen: SpeechIndexScreen, loguru_sink: list[str]
    ) -> None:
        """A stale or hand-edited settings file: no prefix has been pressed yet."""
        assert screen.treeview_index_node is not None
        screen.treeview_index_node.saved_state["prefix"] = "zz-zzz"

        screen._populate_top_alphabet_split_menu("A")

        assert screen._selected_prefix_button is screen._prefix_buttons["a-aa"]
        assert 'Invalid restored prefix: "zz-zzz".' in loguru_sink

    @pytest.mark.parametrize("split", [{}, {"q": {}}])
    def test_a_letter_with_no_words_shows_an_empty_bar_and_the_no_items_row(
        self, screen: SpeechIndexScreen, split: dict[str, dict[str, list[str]]]
    ) -> None:
        """The alphabet is fixed; a rebuilt index may leave a letter out."""
        screen._cleaned_alpha_split_terms = split
        screen._selected_prefix_button = MagicMock()

        screen._populate_top_alphabet_split_menu("Q")

        assert screen._prefix_buttons == {}
        assert screen._selected_prefix_button is None
        assert screen._get_items_for_letter("Q") == []
        cast("MagicMock", screen._populate_index_grid).assert_called_once_with("Q")
        # The rotating background has no words to pick from, and says nothing of it.
        screen._selected_letter_button = MagicMock(text="Q")
        screen._next_background_image()
        screen._random_title_images.get_random_image.assert_not_called()


class TestSpeechIndexScreen:
    def test_init(self, speech_index_screen: SpeechIndexScreen) -> None:
        assert speech_index_screen._search is not None
        assert speech_index_screen._cleaned_alpha_split_terms is not None

    def test_populate_top_alphabet_split_menu(self, speech_index_screen: SpeechIndexScreen) -> None:
        # Mock IndexPrefixButton
        with patch.object(barks_reader.ui.speech_index_screen, "IndexPrefixButton") as mock_btn_cls:
            mock_btn = MagicMock()
            mock_btn.prefix = "apple"
            mock_btn.letter = "A"
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
        mock_button.prefix = "ant"
        mock_button.letter = "A"

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
            mock_btn_cls.side_effect = _mock_prefix_button

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
            mock_btn_cls.side_effect = _mock_prefix_button

            speech_index_screen._populate_top_alphabet_split_menu("A")
            assert set(speech_index_screen._prefix_buttons) == {"apple", "ant"}

            speech_index_screen._populate_top_alphabet_split_menu("B")
            assert set(speech_index_screen._prefix_buttons) == {"banana"}

    def test_prefix_buttons_keep_the_canonical_prefix_off_their_display_text(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        """The bar shows a stacked range but everything else is keyed by the prefix."""
        speech_index_screen._cleaned_alpha_split_terms = {
            "s": {
                "sho-shy": ["shop", "shy"],
                "ska": ["skate", "skating"],
            }
        }
        with (
            patch.object(barks_reader.ui.speech_index_screen, "IndexPrefixButton") as mock_btn_cls,
            patch.object(speech_index_screen, "_populate_index_grid"),
        ):
            mock_btn_cls.side_effect = _mock_prefix_button

            speech_index_screen._populate_top_alphabet_split_menu("S")

            assert set(speech_index_screen._prefix_buttons) == {"sho-shy", "ska"}
            assert speech_index_screen._prefix_buttons["sho-shy"].text == "sho\nshy"
            # A single-prefix bucket has no range to stack, so it stays on one line.
            assert speech_index_screen._prefix_buttons["ska"].text == "ska"

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
                loader = cast("MagicMock", speech_index_screen._texture_loader)
                loader.load_texture.assert_called()
                # The caption comes with the picture, once it has loaded.
                assert speech_index_screen.current_title_str == ""
                loader.load_texture.call_args.args[1](MagicMock(), None)
                assert speech_index_screen.current_title_str != ""

    def test_handle_title_from_bubble_press(self, speech_index_screen: SpeechIndexScreen) -> None:
        mock_callback = MagicMock()
        mock_after_goto = MagicMock()
        speech_index_screen.on_goto_title = mock_callback
        speech_index_screen.on_after_popup_goto_title = mock_after_goto
        speech_index_screen._bubble_title_pages = ("2", "5")  # the row's pages, the popup's title's

        with patch.object(Clock, "schedule_once") as mock_schedule:
            speech_index_screen._handle_title_from_bubble_press(
                "Donald Duck Finds Pirate Gold", "5"
            )

            speech_index_screen._speech_bubble_browser_popup.dismiss.assert_called_once()

            # Execute lambda
            args, _ = mock_schedule.call_args
            args[0](0)

            mock_callback.assert_called()
            # Every page the row lists steps in the title view, not just the one pressed.
            assert mock_callback.call_args.args[1:] == ("5", ("2", "5"))
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

    def test_a_title_row_pressed_by_mouse_takes_the_ring_off_the_speech_button(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        """The focus follows the press onto the row itself, and off the prefix bar."""
        speech_index_screen._nav_on_speech_btn = True
        with (
            patch.object(
                barks_reader.ui.index_screen.IndexScreen, "_place_focus_on", return_value=True
            ),
            patch.object(speech_index_screen, "_clear_prefix_focus") as clear_prefix,
        ):
            assert speech_index_screen._place_focus_on(MagicMock()) is True
        assert speech_index_screen._nav_on_speech_btn is False
        clear_prefix.assert_called_once_with()

    def test_a_press_on_no_row_of_the_columns_leaves_the_focus_as_it_was(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen._nav_on_speech_btn = True
        with (
            patch.object(
                barks_reader.ui.index_screen.IndexScreen, "_place_focus_on", return_value=False
            ),
            patch.object(speech_index_screen, "_clear_prefix_focus") as clear_prefix,
        ):
            assert speech_index_screen._place_focus_on(MagicMock()) is False
        assert speech_index_screen._nav_on_speech_btn is True
        clear_prefix.assert_not_called()

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


# ---------------------------------------------------------------------------
# Paths no GUI test walks: the speech button's other keys, the prefix bar's
# edges, the search cache's cap, and the grid's odd cases.
# ---------------------------------------------------------------------------

_speech_module = barks_reader.ui.speech_index_screen


def test_the_search_cache_drops_its_oldest_entry_when_full() -> None:
    cache: dict[object, int] = {n: n for n in range(_SEARCH_CACHE_MAX_ENTRIES)}
    _store_bounded(cache, "new", -1)
    assert len(cache) == _SEARCH_CACHE_MAX_ENTRIES
    assert 0 not in cache
    assert cache["new"] == -1


def test_an_entity_item_is_found_by_entity(speech_index_screen: SpeechIndexScreen) -> None:
    item = IndexItem(id="Scrooge", display_text="Scrooge", entity_type=EntityType.PERSON)
    speech_index_screen._find_words_for_item(item)
    search = cast("MagicMock", speech_index_screen._search)
    search.find_entities.assert_called_once_with(str(EntityType.PERSON), "Scrooge")


def test_an_open_popup_takes_the_keys(speech_index_screen: SpeechIndexScreen) -> None:
    popup_nav = cast("MagicMock", speech_index_screen._popup_nav)
    popup_nav.is_open = True
    popup_nav.handle_key.return_value = True
    assert speech_index_screen.handle_key(KEY_DOWN) is True
    popup_nav.handle_key.assert_called_once_with(KEY_DOWN)


def test_no_items_for_a_letter_shows_a_row_that_says_so(
    speech_index_screen: SpeechIndexScreen,
) -> None:
    with patch.object(_speech_module, "IndexItemButton") as button_cls:
        speech_index_screen._get_no_items_button("Q")
    assert button_cls.call_args.kwargs["text"] == "*** No index items for 'Q' ***"


def test_a_letter_with_more_prefixes_than_the_bar_holds_is_logged(
    speech_index_screen: SpeechIndexScreen, loguru_sink: list[str]
) -> None:
    limit = _speech_module.MAX_PREFIX_BUTTONS_PER_LETTER
    speech_index_screen._cleaned_alpha_split_terms = {
        "z": {f"p{n}": [f"p{n}"] for n in range(limit + 1)}
    }
    with (
        patch.object(_speech_module, "IndexPrefixButton"),
        patch.object(speech_index_screen, "on_letter_prefix_press"),
    ):
        speech_index_screen._populate_top_alphabet_split_menu("Z")
    assert any("prefix buttons but the bar holds" in line for line in loguru_sink)


_COLUMN_WIDTH = 200
_ROW_HEIGHT = 20
_SUB_ITEMS_HEIGHT = 60


def _column(rows: int) -> BoxLayout:
    column = BoxLayout(orientation="vertical", size_hint=(None, None), width=_COLUMN_WIDTH)
    for n in range(rows):
        column.add_widget(Button(text=f"row {n}", size_hint_y=None, height=_ROW_HEIGHT))
    return column


def _row(column: BoxLayout, from_top: int) -> Button:
    return column.children[len(column.children) - 1 - from_top]


def _row_above(column: BoxLayout, widget: Widget) -> Widget:
    """Return what is drawn just above `widget`: a column's children run bottom to top."""
    return column.children[column.children.index(widget) + 1]


class TestSubItemsInARealGrid:
    """The sub-items go into real columns: where they reach, the rows there move down."""

    @pytest.fixture
    def screen(self, speech_index_screen: SpeechIndexScreen) -> SpeechIndexScreen:
        speech_index_screen.ids.left_column_layout = _column(6)
        speech_index_screen.ids.middle_column_layout = _column(6)
        speech_index_screen.ids.right_column_layout = _column(6)
        speech_index_screen._open_tag_widgets = []
        speech_index_screen._open_tag_button = None
        return speech_index_screen

    @staticmethod
    def _columns(screen: SpeechIndexScreen) -> tuple[BoxLayout, BoxLayout, BoxLayout]:
        return (
            screen.ids.left_column_layout,
            screen.ids.middle_column_layout,
            screen.ids.right_column_layout,
        )

    @staticmethod
    def _open(
        screen: SpeechIndexScreen, column: BoxLayout, from_top: int, sub_items_width: float
    ) -> tuple[Button, Widget, MagicMock]:
        """Open sub-items of a given width under a row, up to the frame the spacers wait for.

        Returns the row's button, its sub-items' wrapper and the patched scheduler,
        whose last call is the spacers'.
        """
        button = _row(column, from_top)
        screen._open_tag_button = button
        sub_items = Widget(size_hint=(None, None))
        with patch.object(_speech_module.Clock, "schedule_once") as scheduled:
            screen._insert_title_sub_items_layout(sub_items)
        wrapper = sub_items.parent
        # What the layout pass does before the next frame.
        wrapper.width = column.width
        sub_items.size = (sub_items_width, _SUB_ITEMS_HEIGHT)
        return button, wrapper, scheduled

    @staticmethod
    def _next_frame(scheduled: MagicMock) -> None:
        scheduled.call_args.args[0](0)

    @staticmethod
    def _spacers(column: BoxLayout) -> list[Widget]:
        return [child for child in column.children if not isinstance(child, (Button, Layout))]

    def test_the_sub_items_go_in_just_under_their_row(self, screen: SpeechIndexScreen) -> None:
        left, _, _ = self._columns(screen)

        button, wrapper, _ = self._open(screen, left, 2, sub_items_width=150)

        assert _row_above(left, wrapper) is button
        assert wrapper.height == _SUB_ITEMS_HEIGHT
        assert screen._is_open_owner(button)

    def test_sub_items_no_wider_than_their_column_move_no_other_row(
        self, screen: SpeechIndexScreen
    ) -> None:
        left, middle, right = self._columns(screen)

        _, _, scheduled = self._open(screen, left, 2, sub_items_width=_COLUMN_WIDTH)
        self._next_frame(scheduled)

        assert self._spacers(middle) == []
        assert self._spacers(right) == []

    def test_wide_sub_items_push_down_the_rows_of_the_column_to_the_right(
        self, screen: SpeechIndexScreen
    ) -> None:
        left, middle, right = self._columns(screen)

        button, _, scheduled = self._open(screen, middle, 2, sub_items_width=300)
        self._next_frame(scheduled)

        (spacer,) = self._spacers(right)
        assert spacer.height == _SUB_ITEMS_HEIGHT
        assert _row_above(right, spacer) is _row(right, 2)
        assert spacer.owner_button is button
        assert self._spacers(left) == []

    def test_sub_items_wider_than_two_columns_push_down_both_to_the_right(
        self, screen: SpeechIndexScreen
    ) -> None:
        left, middle, right = self._columns(screen)

        _, _, scheduled = self._open(screen, left, 0, sub_items_width=2 * _COLUMN_WIDTH + 1)
        self._next_frame(scheduled)

        assert len(self._spacers(middle)) == 1
        assert len(self._spacers(right)) == 1

    def test_the_right_columns_wide_sub_items_push_down_the_middle_columns_rows(
        self, screen: SpeechIndexScreen
    ) -> None:
        # Drawn back from the right edge, they lay over the middle column's rows.
        left, middle, right = self._columns(screen)

        button, wrapper, scheduled = self._open(screen, right, 2, sub_items_width=300)
        self._next_frame(scheduled)

        assert wrapper.children[0].x < 0
        (spacer,) = self._spacers(middle)
        assert spacer.height == _SUB_ITEMS_HEIGHT
        assert _row_above(middle, spacer) is _row(middle, 2)
        assert spacer.owner_button is button
        assert self._spacers(left) == []

    def test_the_right_columns_widest_sub_items_reach_the_left_column_too(
        self, screen: SpeechIndexScreen
    ) -> None:
        left, middle, right = self._columns(screen)

        _, _, scheduled = self._open(screen, right, 2, sub_items_width=2 * _COLUMN_WIDTH)
        self._next_frame(scheduled)

        assert len(self._spacers(middle)) == 1
        assert len(self._spacers(left)) == 1

    def test_the_right_columns_narrow_sub_items_stay_at_its_left_edge(
        self, screen: SpeechIndexScreen
    ) -> None:
        _, middle, right = self._columns(screen)

        _, wrapper, scheduled = self._open(screen, right, 2, sub_items_width=150)
        self._next_frame(scheduled)

        assert wrapper.children[0].x == 0
        assert self._spacers(middle) == []

    def test_a_spacer_under_a_shorter_column_goes_to_its_foot(
        self, screen: SpeechIndexScreen
    ) -> None:
        screen.ids.right_column_layout = _column(2)
        _, middle, right = self._columns(screen)

        _, _, scheduled = self._open(screen, middle, 4, sub_items_width=300)
        self._next_frame(scheduled)

        assert right.children[0] in self._spacers(right)

    def test_closing_takes_the_sub_items_and_their_spacers_out(
        self, screen: SpeechIndexScreen
    ) -> None:
        _, middle, right = self._columns(screen)
        button, wrapper, scheduled = self._open(screen, middle, 2, sub_items_width=300)
        self._next_frame(scheduled)

        screen._close_open_widgets_from(0)

        assert wrapper.parent is None
        assert self._spacers(right) == []
        assert not screen._is_open_owner(button)

    def test_closed_again_before_the_frame_no_spacer_is_left_behind(
        self, screen: SpeechIndexScreen
    ) -> None:
        # The spacer went in all the same: a blank gap, and the item read as still open.
        _, middle, right = self._columns(screen)
        button, _, scheduled = self._open(screen, middle, 2, sub_items_width=300)

        screen._close_open_widgets_from(0)
        self._next_frame(scheduled)

        assert self._spacers(right) == []
        assert screen._open_tag_widgets == []
        assert not screen._is_open_owner(button)

    def test_a_spacer_belongs_to_the_item_opened_not_to_one_pressed_since(
        self, screen: SpeechIndexScreen
    ) -> None:
        _, middle, right = self._columns(screen)
        button, _, scheduled = self._open(screen, middle, 2, sub_items_width=300)

        screen._open_tag_button = _row(middle, 4)
        self._next_frame(scheduled)

        (spacer,) = self._spacers(right)
        assert spacer.owner_button is button

    def test_sub_items_with_no_height_yet_wait_another_frame(
        self, screen: SpeechIndexScreen
    ) -> None:
        _, middle, right = self._columns(screen)
        _, wrapper, _ = self._open(screen, middle, 2, sub_items_width=300)
        sub_items = wrapper.children[0]
        sub_items.height = 0

        with patch.object(_speech_module.Clock, "schedule_once") as scheduled:
            screen._add_spacers_to_columns(0, wrapper, sub_items, 2)
        assert self._spacers(right) == []

        sub_items.height = _SUB_ITEMS_HEIGHT
        self._next_frame(scheduled)
        assert len(self._spacers(right)) == 1

    def test_sub_items_in_no_column_add_nothing(self, screen: SpeechIndexScreen) -> None:
        _, _, right = self._columns(screen)
        wrapper = Widget()
        screen._open_tag_widgets.append(wrapper)

        screen._add_spacers_to_columns(0, wrapper, Widget(width=300, height=40), 0)

        assert self._spacers(right) == []


class TestTheTitleRowsOfATerm:
    """The sub-items themselves: a title row and its speech button for each title found."""

    @pytest.fixture
    def layout(self, speech_index_screen: SpeechIndexScreen) -> Generator[GridLayout]:
        screen = speech_index_screen
        screen.index_theme.SUB_ITEM_INDENT_STEP = 20
        screen.index_theme.TITLE_TEXT = (0, 0, 0, 1)
        screen.index_theme.TITLE_BG = (0, 0, 0, 0.1)
        screen.index_theme.TITLE_BG_SELECTED = (0, 0, 1, 1)
        screen._font_manager.index_title_item_font_name = "Roboto"
        screen._font_manager.index_title_item_font_size = 14
        screen._open_tag_button = Button(padding=[10, 0, 0, 0])
        rows = [
            ("Title One", "3", "Title One, 3", "info one"),
            ("A Much Longer Title Two", "7", "A Much Longer Title Two, 7, 9", "info two"),
        ]
        with (
            patch.object(screen, "_get_sub_items_data", return_value=rows),
            patch.object(_speech_module, "title_row_item", side_effect=lambda *row: row),
        ):
            yield screen._get_title_sub_items_layout(IndexItem("duck", "duck"))

    @staticmethod
    def _rows(layout: GridLayout) -> list[tuple[Button, Button]]:
        widgets = list(reversed(layout.children))
        return list(zip(widgets[::2], widgets[1::2], strict=True))

    def test_each_title_has_a_row_and_a_speech_button(self, layout: GridLayout) -> None:
        rows = self._rows(layout)

        assert [title.text for title, _ in rows] == [
            "Title One, 3",
            "A Much Longer Title Two, 7, 9",
        ]
        assert all(isinstance(title, _SpeechIndexTitleItemButton) for title, _ in rows)
        assert all(isinstance(speech, TitleShowSpeechButton) for _, speech in rows)

    def test_the_rows_are_all_as_wide_as_the_longest_and_indented_under_the_term(
        self, layout: GridLayout
    ) -> None:
        (short, _), (long, _) = self._rows(layout)

        assert short.width == long.width
        assert long.width > long.texture_size[0] > short.texture_size[0]
        assert short.padding[0] == 10 + 20

    def test_a_title_row_goes_to_its_title_at_its_first_page(
        self, speech_index_screen: SpeechIndexScreen, layout: GridLayout
    ) -> None:
        (_, _), (title, _) = self._rows(layout)

        with patch.object(speech_index_screen, "_handle_title") as handle_title:
            title.dispatch("on_release")

        handle_title.assert_called_once_with(
            title,
            ("A Much Longer Title Two", "7", "A Much Longer Title Two, 7, 9", "info two"),
        )

    def test_a_speech_button_shows_the_terms_bubbles_in_its_title(
        self, speech_index_screen: SpeechIndexScreen, layout: GridLayout
    ) -> None:
        (_, speech), _ = self._rows(layout)

        with patch.object(speech_index_screen, "_show_title_speech_bubbles") as show:
            speech.dispatch("on_release")

        show.assert_called_once_with("Title One", "duck", "info one")

    def test_adding_the_sub_items_builds_and_inserts_them(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        item = IndexItem("duck", "duck")
        speech_index_screen._open_tag_item = item
        with (
            patch.object(speech_index_screen, "_get_title_sub_items_layout") as build,
            patch.object(speech_index_screen, "_insert_title_sub_items_layout") as insert,
        ):
            speech_index_screen._add_title_sub_items(0)

        build.assert_called_once_with(item)
        insert.assert_called_once_with(build.return_value)


class TestAPrefixPressedByMouse:
    @staticmethod
    def _real_prefix_buttons(screen: SpeechIndexScreen) -> dict[str, IndexPrefixButton]:
        with patch.object(screen, "_populate_index_grid"):
            screen._populate_top_alphabet_split_menu("A")
        return screen._prefix_buttons

    def test_the_focus_follows_the_press_off_the_grid_it_replaced(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        # Left on row 40 of the old grid, the next Down went to row 41 of the new one.
        screen = speech_index_screen
        buttons = self._real_prefix_buttons(screen)
        screen.ids.alphabet_top_split_layout.children = list(reversed(buttons.values()))
        screen._nav_active = True
        screen._nav_panel = _IndexNavPanel.ITEMS
        screen._nav_focused_item_idx = 40

        with (
            patch.object(screen, "_populate_index_grid"),
            patch.object(screen, "_clear_all_item_focus") as clear_items,
            patch.object(screen, "_clear_letter_focus"),
            patch.object(_speech_module, "draw_focus_highlight") as draw,
        ):
            buttons["ant"].dispatch("on_release")

        assert screen._nav_panel is _IndexNavPanel.PREFIX
        assert screen._selected_prefix_button is buttons["ant"]
        assert screen._nav_focused_prefix_idx == list(buttons).index("ant")
        clear_items.assert_called()
        draw.assert_called_once_with(buttons["ant"], _speech_module.INDEX_NAV_FOCUS_GROUP)

    def test_with_the_keys_elsewhere_a_press_draws_no_focus(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        screen = speech_index_screen
        buttons = self._real_prefix_buttons(screen)
        screen._nav_active = False

        with (
            patch.object(screen, "_populate_index_grid") as populate,
            patch.object(screen, "_enter_prefix_panel") as enter_prefix,
        ):
            buttons["ant"].dispatch("on_release")

        populate.assert_called_once_with("A")
        enter_prefix.assert_not_called()


class TestEnterOnAPrefix:
    """Enter shows the prefix, and the focus drops into its grid on the next frame."""

    @pytest.fixture
    def entered(
        self, speech_index_screen: SpeechIndexScreen
    ) -> Generator[tuple[MagicMock, MagicMock]]:
        """Press Enter on a prefix; yield the scheduler holding the deferred move, and the move."""
        screen = speech_index_screen
        screen.ids.alphabet_top_split_layout.children = [MagicMock(), MagicMock()]
        screen._nav_focused_prefix_idx = 0
        screen._nav_active = True
        screen._nav_panel = _IndexNavPanel.PREFIX
        screen._grid_version = 7
        with (
            patch.object(screen, "_clear_prefix_focus"),
            patch.object(screen, "on_letter_prefix_press"),
            patch.object(screen, "_enter_items_panel") as enter_items,
            patch.object(_speech_module.Clock, "schedule_once") as scheduled,
        ):
            assert screen._handle_prefix_key(KEY_ENTER) is True
            enter_items.assert_not_called()
            yield scheduled, enter_items

    @staticmethod
    def _next_frame(scheduled: MagicMock) -> None:
        scheduled.call_args.args[0](0)

    def test_the_focus_enters_the_new_grid_on_the_next_frame(
        self, entered: tuple[MagicMock, MagicMock]
    ) -> None:
        scheduled, enter_items = entered
        self._next_frame(scheduled)

        enter_items.assert_called_once_with()

    def test_the_keys_having_left_the_screen_no_focus_is_drawn(
        self, speech_index_screen: SpeechIndexScreen, entered: tuple[MagicMock, MagicMock]
    ) -> None:
        speech_index_screen._nav_active = False

        scheduled, enter_items = entered
        self._next_frame(scheduled)

        enter_items.assert_not_called()

    def test_the_focus_having_gone_to_the_alphabet_stays_there(
        self, speech_index_screen: SpeechIndexScreen, entered: tuple[MagicMock, MagicMock]
    ) -> None:
        speech_index_screen._nav_panel = _IndexNavPanel.ALPHABET

        scheduled, enter_items = entered
        self._next_frame(scheduled)

        enter_items.assert_not_called()

    def test_another_prefix_shown_since_keeps_the_focus_on_the_bar(
        self, speech_index_screen: SpeechIndexScreen, entered: tuple[MagicMock, MagicMock]
    ) -> None:
        speech_index_screen._grid_version += 1

        scheduled, enter_items = entered
        self._next_frame(scheduled)

        enter_items.assert_not_called()


class TestSpeechButtonOtherKeys:
    @staticmethod
    def _on_speech_button(screen: SpeechIndexScreen) -> None:
        screen._nav_on_speech_btn = True
        screen._nav_focused_col = 0
        screen._nav_focused_item_idx = 0

    def test_right_moves_to_the_next_columns_title_row(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        self._on_speech_button(speech_index_screen)
        speech_index_screen.num_columns = 2
        with (
            patch.object(speech_index_screen, "_get_col_buttons", return_value=[MagicMock()]),
            patch.object(speech_index_screen, "_move_col_focus") as moved,
        ):
            assert speech_index_screen._handle_items_key(KEY_RIGHT) is True
        moved.assert_called_once_with(1)
        assert speech_index_screen._nav_on_speech_btn is False

    def test_right_from_the_last_column_stays_on_the_speech_button(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        self._on_speech_button(speech_index_screen)
        speech_index_screen.num_columns = 1
        with patch.object(speech_index_screen, "_move_col_focus") as moved:
            assert speech_index_screen._handle_items_key(KEY_RIGHT) is True
        moved.assert_not_called()
        assert speech_index_screen._nav_on_speech_btn is True

    def test_a_page_key_scrolls_as_from_a_title_row(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        self._on_speech_button(speech_index_screen)
        start = 0.5
        speech_index_screen.ids.index_scroll_view.scroll_y = start
        assert speech_index_screen._handle_items_key(KEY_PAGE_DOWN) is True
        assert speech_index_screen.ids.index_scroll_view.scroll_y < start

    def test_no_title_rows_draw_no_focus(self, speech_index_screen: SpeechIndexScreen) -> None:
        self._on_speech_button(speech_index_screen)
        with (
            patch.object(speech_index_screen, "_get_col_buttons", return_value=[]),
            patch.object(_speech_module, "draw_focus_highlight") as drawn,
        ):
            speech_index_screen._draw_item_focus()
        drawn.assert_not_called()


class TestPairedSpeechButtonOddCases:
    def test_a_title_button_its_parent_no_longer_holds(self) -> None:
        title_btn = MagicMock(spec=_SpeechIndexTitleItemButton)
        title_btn.parent = MagicMock(children=[MagicMock()])
        assert SpeechIndexScreen._get_paired_speech_button(title_btn) is None

    def test_a_title_button_with_no_speech_button_beside_it(self) -> None:
        title_btn = MagicMock(spec=_SpeechIndexTitleItemButton)
        title_btn.parent = MagicMock(children=[MagicMock(), title_btn])  # a plain neighbour
        assert SpeechIndexScreen._get_paired_speech_button(title_btn) is None


class TestPrefixBarEdges:
    @staticmethod
    def _visible(screen: SpeechIndexScreen, count: int) -> list[MagicMock]:
        buttons = [MagicMock(text=f"p{n}") for n in range(count)]
        screen.ids.alphabet_top_split_layout.children = list(reversed(buttons))
        return buttons

    def test_left_along_the_bar_selects_the_prefix_before(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        buttons = self._visible(speech_index_screen, 3)
        speech_index_screen._nav_focused_prefix_idx = 2
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus"),
            patch.object(speech_index_screen, "_draw_prefix_focus"),
            patch.object(speech_index_screen, "on_letter_prefix_press") as press,
        ):
            assert speech_index_screen._handle_prefix_key(KEY_LEFT) is True
        assert speech_index_screen._nav_focused_prefix_idx == 1
        press.assert_called_once_with(buttons[1])

    def test_escape_goes_back_to_the_alphabet(self, speech_index_screen: SpeechIndexScreen) -> None:
        self._visible(speech_index_screen, 2)
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus"),
            patch.object(speech_index_screen, "_enter_alphabet_panel") as alphabet,
        ):
            assert speech_index_screen._handle_prefix_key(KEY_ESCAPE) is True
        alphabet.assert_called_once()

    def test_an_empty_bar_takes_no_key(self, speech_index_screen: SpeechIndexScreen) -> None:
        self._visible(speech_index_screen, 0)
        assert speech_index_screen._handle_prefix_key(KEY_LEFT) is False

    def test_entering_the_bar_with_no_prefix_selected_focuses_the_first(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        self._visible(speech_index_screen, 2)
        speech_index_screen._selected_prefix_button = None
        speech_index_screen._nav_focused_prefix_idx = 1
        with (
            patch.object(speech_index_screen, "_clear_all_item_focus"),
            patch.object(speech_index_screen, "_clear_letter_focus"),
            patch.object(speech_index_screen, "_draw_prefix_focus"),
        ):
            speech_index_screen._enter_prefix_panel()
        assert speech_index_screen._nav_panel is _IndexNavPanel.PREFIX
        assert speech_index_screen._nav_focused_prefix_idx == 0

    def test_backing_out_of_the_items_goes_to_the_bar(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        with patch.object(speech_index_screen, "_enter_prefix_panel") as prefix:
            speech_index_screen._on_back_from_items()
        prefix.assert_called_once()

    def test_up_from_the_first_item_goes_to_the_bar(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        with (
            patch.object(speech_index_screen, "_clear_all_item_focus"),
            patch.object(speech_index_screen, "_enter_prefix_panel") as prefix,
        ):
            speech_index_screen._on_up_from_first_item()
        prefix.assert_called_once()

    def test_leaving_nav_mode_clears_the_bars_focus(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen._nav_active = True
        with (
            patch.object(speech_index_screen, "_clear_prefix_focus") as cleared,
            patch.object(speech_index_screen, "_clear_letter_focus"),
            patch.object(speech_index_screen, "_clear_all_item_focus"),
        ):
            speech_index_screen.exit_nav_focus()
        cleared.assert_called_once()
        assert speech_index_screen._nav_active is False


class TestSpeechButtonDeadEnds:
    """Keys on a title row whose speech button has gone, or with no rows at all."""

    @staticmethod
    def _unpaired_title(screen: SpeechIndexScreen) -> MagicMock:
        title_btn = MagicMock(spec=_SpeechIndexTitleItemButton)
        title_btn.parent = MagicMock(children=[MagicMock(), title_btn])
        screen._nav_focused_col = 0
        screen._nav_focused_item_idx = 0
        return title_btn

    def test_a_title_row_with_no_speech_button_draws_no_focus(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        title_btn = self._unpaired_title(speech_index_screen)
        speech_index_screen._nav_on_speech_btn = True
        speech_index_screen._nav_focused_btn = None
        with (
            patch.object(speech_index_screen, "_get_col_buttons", return_value=[title_btn]),
            patch.object(_speech_module, "draw_focus_highlight") as drawn,
        ):
            speech_index_screen._draw_item_focus()
        drawn.assert_not_called()
        assert speech_index_screen._nav_focused_btn is None

    def test_enter_with_no_title_rows_is_taken_and_does_nothing(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen._nav_on_speech_btn = True
        speech_index_screen._nav_focused_col = 0
        speech_index_screen._nav_focused_item_idx = 0
        with patch.object(speech_index_screen, "_get_col_buttons", return_value=[]):
            assert speech_index_screen._handle_items_key(KEY_ENTER) is True

    def test_enter_on_a_title_row_with_no_speech_button_opens_nothing(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        title_btn = self._unpaired_title(speech_index_screen)
        speech_index_screen._nav_on_speech_btn = True
        neighbour = title_btn.parent.children[0]
        with patch.object(speech_index_screen, "_get_col_buttons", return_value=[title_btn]):
            assert speech_index_screen._handle_items_key(KEY_ENTER) is True
        neighbour.trigger_action.assert_not_called()

    def test_right_with_no_title_rows_goes_on_to_the_grid(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen._nav_on_speech_btn = False
        speech_index_screen._nav_focused_col = 0
        speech_index_screen._nav_focused_item_idx = 0
        with (
            patch.object(speech_index_screen, "_get_col_buttons", return_value=[]),
            patch.object(
                barks_reader.ui.index_screen.IndexScreen, "_handle_items_key", return_value=True
            ) as grid_key,
        ):
            assert speech_index_screen._handle_items_key(KEY_RIGHT) is True
        grid_key.assert_called_once_with(KEY_RIGHT)
        assert speech_index_screen._nav_on_speech_btn is False


class TestSearchCaches:
    def test_a_letter_with_no_terms_changes_no_background(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen._selected_letter_button = MagicMock(text="Q")
        speech_index_screen._item_index["Q"] = []
        speech_index_screen._next_background_image()
        speech_index_screen._random_title_images.get_random_image.assert_not_called()

    def test_a_term_searched_before_is_not_searched_again_for_a_background(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        item = IndexItem("term", "term")
        speech_index_screen._selected_letter_button = MagicMock(text="T")
        speech_index_screen._item_index["T"] = [item]
        speech_index_screen._background_titles_cache[item] = ["Donald Duck Finds Pirate Gold"]
        with (
            patch.object(speech_index_screen, "_find_words_for_item") as searched,
            patch.object(speech_index_screen, "_set_background_image") as set_background,
        ):
            speech_index_screen._next_background_image()
        searched.assert_not_called()
        (found_titles,) = speech_index_screen._random_title_images.get_random_image.call_args.args
        assert found_titles == [
            _speech_module.ALL_FANTA_COMIC_BOOK_INFO[Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]
        ]
        set_background.assert_called_once()

    def test_a_term_searched_before_is_not_searched_again_for_its_titles(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        item = IndexItem("term", "term")
        speech_index_screen._found_words_cache[item] = {}
        with patch.object(speech_index_screen, "_find_words_for_item") as searched:
            assert speech_index_screen._get_sub_items_data(item) == []
        searched.assert_not_called()


def test_a_bubble_goto_with_no_focus_hand_off_still_goes_to_the_title(
    speech_index_screen: SpeechIndexScreen,
) -> None:
    goto = MagicMock()
    speech_index_screen.on_goto_title = goto
    speech_index_screen.on_after_popup_goto_title = None
    with patch.object(Clock, "schedule_once") as schedule:
        speech_index_screen._handle_title_from_bubble_press("Donald Duck Finds Pirate Gold", "5")
    schedule.call_args.args[0](0)
    goto.assert_called_once()


def test_a_bubble_goto_to_a_title_in_no_volume_is_a_notice_not_a_crash(
    speech_index_screen: SpeechIndexScreen, mock_user_error_handler: MagicMock
) -> None:
    """The bubble goto runs on the Kivy clock: uncaught there, the error ended the app."""
    title = Titles.JINXED_JALOPY_RACE_THE
    assert title not in _speech_module.ALL_FANTA_COMIC_BOOK_INFO
    speech_index_screen.on_goto_title = MagicMock(side_effect=TitleNotInFantaInfoError("Jalopy"))
    hand_off = MagicMock()
    speech_index_screen.on_after_popup_goto_title = hand_off
    with patch.object(Clock, "schedule_once") as schedule:
        speech_index_screen._handle_title_from_bubble_press(ENUM_TO_STR_TITLE[title], "5")
    schedule.call_args.args[0](0)

    error_type, error_info = mock_user_error_handler.handle_error.call_args.args
    assert error_type is ErrorTypes.ArchiveVolumeNotAvailable
    assert error_info.title is title
    # Nothing was gone to, so there is no title portal to take the focus.
    hand_off.assert_not_called()


def test_a_background_word_spoken_only_outside_the_volumes_does_not_raise(
    speech_index_screen: SpeechIndexScreen,
) -> None:
    """Every title has a name; only those in a Fantagraphics volume have an info."""
    title = Titles.JINXED_JALOPY_RACE_THE
    assert title not in _speech_module.ALL_FANTA_COMIC_BOOK_INFO
    item = IndexItem("term", "term")
    speech_index_screen._selected_letter_button = MagicMock(text="T")
    speech_index_screen._item_index["T"] = [item]
    speech_index_screen._background_titles_cache[item] = [
        ENUM_TO_STR_TITLE[title],
        "Donald Duck Finds Pirate Gold",
        "no such story",
    ]
    with patch.object(speech_index_screen, "_set_background_image"):
        speech_index_screen._next_background_image()

    (found_titles,) = speech_index_screen._random_title_images.get_random_image.call_args.args
    assert found_titles == [
        _speech_module.ALL_FANTA_COMIC_BOOK_INFO[Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]
    ]


def test_an_empty_prefix_bar_draws_no_focus(speech_index_screen: SpeechIndexScreen) -> None:
    speech_index_screen.ids.alphabet_top_split_layout.children = []
    with patch.object(_speech_module, "draw_focus_highlight") as drawn:
        speech_index_screen._draw_prefix_focus()
    drawn.assert_not_called()
