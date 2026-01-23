# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.random_title_images import ImageInfo
from barks_reader.speech_index_screen import IndexItem, SpeechIndexScreen

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.file_paths.barks_panels_are_encrypted = False
    settings.sys_file_paths.get_barks_reader_indexes_dir.return_value = "indexes_dir"
    return settings


@pytest.fixture
def mock_font_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture
def speech_index_screen(
    mock_settings: MagicMock, mock_font_manager: MagicMock
) -> Generator[SpeechIndexScreen]:
    # Patch IndexScreen.__init__ to avoid Kivy widget initialization
    with patch("barks_reader.index_screen.IndexScreen.__init__"):  # noqa: SIM117
        with (
            patch("barks_reader.speech_index_screen.SearchEngine") as mock_search_cls,
            patch("barks_reader.speech_index_screen.RandomTitleImages") as mock_random_cls,
            patch("barks_reader.speech_index_screen.PanelTextureLoader") as mock_loader_cls,
            patch("barks_reader.speech_index_screen.SpeechBubblesPopup") as mock_popup_cls,
            patch("barks_reader.speech_index_screen.SpeechIndexScreen._populate_alphabet_menu"),
        ):
            # Setup mock search engine
            mock_indexer = mock_search_cls.return_value
            # Required structure: {letter: {prefix: [terms]}}
            mock_indexer.get_cleaned_alpha_split_lemmatized_terms.return_value = {
                "a": {"apple": ["apple", "apples"], "ant": ["ant"]},
                "b": {"banana": ["banana"]},
            }

            screen = SpeechIndexScreen(mock_settings, mock_font_manager)

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
            screen._whoosh_indexer = mock_indexer
            screen._speech_bubble_browser_popup = mock_popup_cls.return_value

            screen.treeview_index_node = MagicMock()
            screen.treeview_index_node.saved_state = {}
            screen._alphabet_buttons = {}

            yield screen


class TestSpeechIndexScreen:
    def test_init(self, speech_index_screen: SpeechIndexScreen) -> None:
        # noinspection PyProtectedMember
        assert speech_index_screen._whoosh_indexer is not None
        # noinspection PyProtectedMember
        assert speech_index_screen._cleaned_alpha_split_terms is not None

    def test_populate_top_alphabet_split_menu(self, speech_index_screen: SpeechIndexScreen) -> None:
        # Mock IndexMenuButton
        with patch("barks_reader.speech_index_screen.IndexMenuButton") as mock_btn_cls:
            mock_btn = MagicMock()
            mock_btn.text = "apple"
            mock_btn_cls.return_value = mock_btn

            # Mock _populate_index_grid to prevent further chain execution
            with patch.object(speech_index_screen, "_populate_index_grid"):
                # noinspection PyProtectedMember
                speech_index_screen._populate_top_alphabet_split_menu("A")

                # Should create buttons for "apple" and "ant"
                assert mock_btn_cls.call_count == 2  # noqa: PLR2004
                # noinspection LongLine
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

            assert speech_index_screen.treeview_index_node.saved_state["prefix"] == "ant"
            # noinspection PyProtectedMember
            assert speech_index_screen._selected_prefix_button == mock_button

            # Check items populated for "A" (from "ant" prefix)
            # noinspection PyProtectedMember
            items = speech_index_screen._item_index["A"]
            assert len(items) == 1
            assert items[0].display_text == "ant"

            mock_populate_grid.assert_called_with("A")

    def test_find_words(self, speech_index_screen: SpeechIndexScreen) -> None:
        # noinspection PyProtectedMember
        speech_index_screen._find_words("test")
        # noinspection PyProtectedMember
        speech_index_screen._whoosh_indexer.find_all_words.assert_called_with("test")

        # noinspection PyProtectedMember
        speech_index_screen._find_words("1942")
        # noinspection PyProtectedMember
        speech_index_screen._whoosh_indexer.find_unstemmed_words.assert_called_with("1942")

    def test_next_background_image(self, speech_index_screen: SpeechIndexScreen) -> None:
        # Setup state
        mock_selected_letter = MagicMock()
        mock_selected_letter.text = "A"
        # noinspection PyProtectedMember
        speech_index_screen._selected_letter_button = mock_selected_letter

        # Populate item index
        # noinspection PyProtectedMember
        speech_index_screen._item_index["A"] = [IndexItem("term", "term")]

        # Mock find_words
        with patch.object(  # noqa: SIM117
            speech_index_screen, "_find_words", return_value={"Title": MagicMock()}
        ):
            # Mock ALL_FANTA_COMIC_BOOK_INFO lookup
            with patch(
                "barks_reader.speech_index_screen.ALL_FANTA_COMIC_BOOK_INFO"
            ) as mock_all_info:
                mock_info = MagicMock()
                mock_all_info.__getitem__.return_value = mock_info

                # Mock random image
                image_info = ImageInfo(
                    filename=Path("img.png"), from_title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
                )
                # noinspection PyProtectedMember
                speech_index_screen._random_title_images.get_random_image.return_value = image_info

                # Execute
                # noinspection PyProtectedMember
                speech_index_screen._next_background_image()

                # Verify
                # noinspection PyProtectedMember
                speech_index_screen._texture_loader.load_texture.assert_called()
                assert speech_index_screen.current_title_str != ""

    def test_handle_title_from_bubble_press(self, speech_index_screen: SpeechIndexScreen) -> None:
        mock_callback = MagicMock()
        speech_index_screen.on_goto_title = mock_callback

        with patch("barks_reader.speech_index_screen.Clock.schedule_once") as mock_schedule:
            # noinspection PyProtectedMember
            speech_index_screen._handle_title_from_bubble_press(
                "Donald Duck Finds Pirate Gold", "5"
            )

            # noinspection PyProtectedMember
            speech_index_screen._speech_bubble_browser_popup.dismiss.assert_called_once()

            # Execute lambda
            args, _ = mock_schedule.call_args
            args[0](0)

            mock_callback.assert_called()
