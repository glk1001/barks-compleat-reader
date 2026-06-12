# ruff: noqa: SLF001

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.speech_index_screen
import pytest
from barks_fantagraphics.entity_types import EntityType
from barks_reader.ui.entity_index_screen import EntityIndexScreen
from barks_reader.ui.index_screen import IndexItem

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.file_paths.barks_panels_are_encrypted = False
    settings.sys_file_paths.get_barks_reader_indexes_dir.return_value = "indexes_dir"
    return settings


@contextmanager
def _patched_screen_deps(alpha_split_terms: dict, entity_terms: list[str]) -> Iterator[MagicMock]:
    """Patch the Kivy and search dependencies needed to construct an EntityIndexScreen.

    Yields the mock ComicSearch indexer instance.
    """
    with (
        patch.object(barks_reader.ui.index_screen.IndexScreen, "__init__"),
        patch.object(barks_reader.ui.speech_index_screen, "ComicSearch") as mock_search_cls,
        patch.object(barks_reader.ui.speech_index_screen, "ImageSelector"),
        patch.object(barks_reader.ui.speech_index_screen, "ReaderFilePathsResolver"),
        patch.object(barks_reader.ui.speech_index_screen, "PanelTextureLoader"),
        patch.object(
            barks_reader.ui.speech_index_screen,
            "create_speech_bubble_popup",
            return_value=(MagicMock(), MagicMock()),
        ),
        patch.object(EntityIndexScreen, "_populate_alphabet_menu"),
        patch.object(EntityIndexScreen, "ids", MagicMock()),
    ):
        mock_indexer = mock_search_cls.return_value
        # get_alpha_split_terms is called by SpeechIndexScreen.__init__
        mock_indexer.get_alpha_split_terms.return_value = alpha_split_terms
        # get_entity_terms is called by EntityIndexScreen.__init__
        mock_indexer.get_entity_terms.return_value = entity_terms

        yield mock_indexer


@pytest.fixture
def person_index_screen(
    mock_settings: MagicMock,
    mock_font_manager: MagicMock,
    mock_user_error_handler: MagicMock,
) -> Generator[EntityIndexScreen]:
    with _patched_screen_deps(
        alpha_split_terms={"a": {"al": ["Alice"]}},
        entity_terms=["Daisy Duck", "Donald Duck", "Scrooge McDuck"],
    ) as mock_indexer:
        screen = EntityIndexScreen(
            EntityType.PERSON, mock_settings, mock_font_manager, mock_user_error_handler
        )

        screen.ids = MagicMock()
        screen.index_theme = MagicMock()
        screen._font_manager = mock_font_manager
        screen._search = mock_indexer
        screen.treeview_index_node = MagicMock()
        screen.treeview_index_node.saved_state = {}

        yield screen


class TestEntityIndexScreen:
    def test_item_index_populated_from_entity_terms(
        self, person_index_screen: EntityIndexScreen
    ) -> None:
        """_item_index should be populated from flat entity terms grouped by letter."""
        assert "D" in person_index_screen._item_index
        assert "S" in person_index_screen._item_index
        d_items = person_index_screen._item_index["D"]
        assert len(d_items) == 2  # noqa: PLR2004
        assert d_items[0].id == "Daisy Duck"
        assert d_items[1].id == "Donald Duck"
        s_items = person_index_screen._item_index["S"]
        assert len(s_items) == 1
        assert s_items[0].id == "Scrooge McDuck"

    def test_find_words_dispatches_to_find_entities(
        self, person_index_screen: EntityIndexScreen
    ) -> None:
        person_index_screen._find_words("Donald Duck")
        person_index_screen._search.find_entities.assert_called_with(
            EntityType.PERSON, "Donald Duck"
        )

    def test_entity_type_stored(self, person_index_screen: EntityIndexScreen) -> None:
        assert person_index_screen._entity_type == EntityType.PERSON

    def test_populate_index_for_letter_skips_prefix_menu(
        self, person_index_screen: EntityIndexScreen
    ) -> None:
        """_populate_index_for_letter should call _populate_index_grid directly."""
        with (
            patch.object(person_index_screen, "_populate_index_grid") as mock_grid,
            patch.object(person_index_screen, "_populate_top_alphabet_split_menu") as mock_prefix,
        ):
            person_index_screen._populate_index_for_letter("D")
            mock_grid.assert_called_once_with("D")
            mock_prefix.assert_not_called()

    def test_on_right_from_alphabet_enters_items(
        self, person_index_screen: EntityIndexScreen
    ) -> None:
        """Right from alphabet should go directly to items, not prefix."""
        with patch.object(person_index_screen, "_enter_items_panel") as mock_enter:
            person_index_screen._on_right_from_alphabet()
            mock_enter.assert_called_once()

    def test_on_back_from_items_enters_alphabet(
        self, person_index_screen: EntityIndexScreen
    ) -> None:
        """Back from items should go to alphabet, not prefix."""
        with patch.object(person_index_screen, "_enter_alphabet_panel") as mock_enter:
            person_index_screen._on_back_from_items()
            mock_enter.assert_called_once()

    def test_get_items_for_letter(self, person_index_screen: EntityIndexScreen) -> None:
        """_get_items_for_letter should return items from _item_index."""
        items = person_index_screen._get_items_for_letter("D")
        assert len(items) == 2  # noqa: PLR2004
        assert all(isinstance(i, IndexItem) for i in items)

    def test_non_alpha_term_raises(
        self,
        mock_settings: MagicMock,
        mock_font_manager: MagicMock,
        mock_user_error_handler: MagicMock,
    ) -> None:
        """Terms with non-alpha first chars (like '-ER-') should raise RuntimeError."""
        with (
            _patched_screen_deps(alpha_split_terms={}, entity_terms=["-ER-", "Alice"]),
            pytest.raises(RuntimeError, match="non-alpha prefix"),
        ):
            EntityIndexScreen(
                EntityType.PERSON,
                mock_settings,
                mock_font_manager,
                mock_user_error_handler,
            )
