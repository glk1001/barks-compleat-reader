# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.speech_index_screen
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.entity_types import EntityType
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
    _SEARCH_CACHE_MAX_ENTRIES,
    SpeechIndexScreen,
    _SpeechIndexTitleItemButton,
    _store_bounded,
    stacked_prefix_label,
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
            mock_btn.prefix = "apple"
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
            mock_btn_cls.side_effect = lambda prefix, text: MagicMock(prefix=prefix, text=text)

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
            mock_btn_cls.side_effect = lambda prefix, text: MagicMock(prefix=prefix, text=text)

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
            mock_btn_cls.side_effect = lambda prefix, text: MagicMock(prefix=prefix, text=text)

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


class TestStackedPrefixLabel:
    def test_a_range_is_stacked_over_two_lines(self) -> None:
        assert stacked_prefix_label("sho-shy", ["shop", "shy"]) == "sho\nshy"

    def test_a_single_prefix_label_stays_on_one_line(self) -> None:
        assert stacked_prefix_label("ska", ["skate", "skating"]) == "ska"

    def test_a_part_may_hold_the_separator_itself(self) -> None:
        """A label like "s-sa" runs "s" to "sa", so the ends cannot come from a split."""
        assert stacked_prefix_label("s-sa", ["s", "sap"]) == "s\nsa"

    def test_ends_that_no_longer_rejoin_fall_back_to_the_prefix(self) -> None:
        """Colliding labels are merged upstream; never show a label for the wrong span."""
        assert stacked_prefix_label("sho-shy", ["about", "zebra"]) == "sho-shy"


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


class TestSpacers:
    def test_a_layout_with_no_height_yet_tries_again_next_frame(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        layout = MagicMock(height=0)
        with patch.object(_speech_module.Clock, "schedule_once") as scheduled:
            speech_index_screen._add_spacers_to_columns(0, MagicMock(), layout, 0)
        scheduled.assert_called_once()

    def test_a_layout_in_no_column_adds_nothing(
        self, speech_index_screen: SpeechIndexScreen
    ) -> None:
        speech_index_screen.ids.middle_column_layout = MagicMock()
        stranger = MagicMock()
        speech_index_screen._add_spacers_to_columns(0, stranger, MagicMock(height=40), 0)
        speech_index_screen.ids.right_column_layout.add_widget.assert_not_called()


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
