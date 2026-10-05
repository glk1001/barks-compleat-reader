# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.main_index_screen
import pytest
from barks_fantagraphics.barks_tags import Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET
from barks_reader.ui.index_screen import IndexItem
from barks_reader.ui.main_index_screen import MainIndexScreen
from kivy.clock import Clock

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.file_paths.barks_panels_are_encrypted = False
    settings.show_fun_view_title_info = True
    return settings


@pytest.fixture
def main_index_screen(
    mock_settings: MagicMock,
    mock_font_manager: MagicMock,
    mock_user_error_handler: MagicMock,
) -> Generator[MainIndexScreen]:
    # Patch the superclass __init__ to avoid Kivy widget initialization
    with patch.object(barks_reader.ui.index_screen.IndexScreen, "__init__"):  # noqa: SIM117
        # Patch dependencies created in __init__
        with (
            patch.object(
                barks_reader.ui.main_index_screen, "ImageSelector"
            ) as mock_random_images_cls,
            patch.object(barks_reader.ui.main_index_screen, "ReaderFilePathsResolver"),
            patch.object(
                barks_reader.ui.main_index_screen, "PanelTextureLoader"
            ) as mock_loader_cls,
            patch.object(MainIndexScreen, "_populate_alphabet_menu"),
        ):
            screen = MainIndexScreen(mock_settings, mock_font_manager, mock_user_error_handler)

            # Manually initialize attributes that super().__init__ or __init__ would set
            screen.ids = MagicMock()
            screen.index_theme = MagicMock()
            screen._font_manager = mock_font_manager
            screen._random_title_images = mock_random_images_cls.return_value
            screen._texture_loader = mock_loader_cls.return_value
            screen._alphabet_buttons = {}
            screen.treeview_index_node = MagicMock()
            screen.treeview_index_node.saved_state = {}

            yield screen


class TestMainIndexScreen:
    def test_init(self, main_index_screen: MainIndexScreen) -> None:
        assert main_index_screen._font_manager is not None
        assert main_index_screen._random_title_images is not None
        assert main_index_screen._texture_loader is not None

    def test_build_index_excludes_individual_covers(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        indexed_ids = {
            item.id for items in main_index_screen._item_index.values() for item in items
        }
        assert not (indexed_ids & COVERS_SET)
        assert Titles.ALL_COVERS in indexed_ids
        assert Titles.DONALD_DUCK_FINDS_PIRATE_GOLD in indexed_ids

    def test_get_items_for_letter(self, main_index_screen: MainIndexScreen) -> None:
        # Clear the index built during init so we can test with controlled data
        main_index_screen._item_index.clear()

        # Manually populate with test items
        main_index_screen._item_index["A"] = [
            IndexItem(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, "Apple"),
            IndexItem(Titles.VICTORY_GARDEN_THE, "Ant, The"),
        ]
        main_index_screen._item_index["B"] = [IndexItem(Titles.RABBITS_FOOT_THE, "Banana")]

        # Test 'A'
        items_a = main_index_screen._get_items_for_letter("A")

        assert len(items_a) == 2  # noqa: PLR2004
        display_texts = [i.display_text for i in items_a]
        assert "Apple" in display_texts
        assert "Ant, The" in display_texts

        # Test 'B'
        items_b = main_index_screen._get_items_for_letter("B")
        assert len(items_b) == 1
        assert items_b[0].display_text == "Banana"

    def test_create_index_button(self, main_index_screen: MainIndexScreen) -> None:
        # Mock item
        item = MagicMock()
        item.display_text = "My Title"

        with patch.object(barks_reader.ui.main_index_screen, "IndexItemButton") as mock_btn_cls:
            btn = main_index_screen._create_index_button(item)

            mock_btn_cls.assert_called_once()
            # Check args
            _, kwargs = mock_btn_cls.call_args
            assert kwargs["text"] == "My Title"
            assert btn is mock_btn_cls.return_value

    def test_on_index_item_press(self, main_index_screen: MainIndexScreen) -> None:
        # MainIndexScreen._on_index_item_press usually navigates to the title.

        mock_item = MagicMock()
        mock_item.id = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_item.page_to_goto = "1"

        mock_button = MagicMock()

        # Mock the callback
        mock_callback = MagicMock()
        main_index_screen.on_goto_title = mock_callback

        # We need to patch Clock to execute the delayed calls
        with patch.object(Clock, "schedule_once") as mock_schedule:
            # Capture lambdas
            callbacks = []

            def side_effect(func, _dt):  # noqa: ANN001, ANN202
                callbacks.append(func)

            mock_schedule.side_effect = side_effect

            main_index_screen._on_index_item_press(mock_button, mock_item)

            # Execute callbacks (highlight, goto, reset)
            for cb in callbacks:
                cb(0)

            # Verify callback called
            mock_callback.assert_called()
            args, _ = mock_callback.call_args
            image_info = args[0]
            page = args[1]

            assert image_info.from_title == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
            assert page == "1"


class TestTagMarkers:
    """The lines a GUI test waits on as a tag or tag group opens beneath its row."""

    def test_opening_a_tag_group_logs_it_and_schedules_its_tags(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        group = next(iter(barks_reader.ui.main_index_screen.BARKS_TAG_GROUPS))
        with patch.object(Clock, "schedule_once") as schedule:
            main_index_screen._handle_tag_group(MagicMock(), IndexItem(group, group.value))
        assert f'Handling tag group: "{group.name}".' in loguru_sink
        schedule.assert_called_once()

    def test_opening_a_tag_logs_it(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        tag = next(iter(barks_reader.ui.main_index_screen.BARKS_TAGGED_TITLES))
        with patch.object(Clock, "schedule_once"):
            main_index_screen._handle_tag(MagicMock(), IndexItem(tag, tag.value))
        assert f'Handling tag: "{tag.name}".' in loguru_sink

    def test_a_tag_no_title_carries_opens_nothing(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        """A tag is indexed whether or not any title carries it, as "My Picks" can be."""
        tag = Tags.PERSONAL_FAVOURITES
        main_index_screen._open_tag_button = MagicMock()

        with (
            patch.object(barks_reader.ui.main_index_screen, "BARKS_TAGGED_TITLES", {}),
            patch.object(Clock, "schedule_once") as schedule,
        ):
            main_index_screen._handle_tag(MagicMock(), IndexItem(tag, tag.value))

        schedule.assert_not_called()
        assert main_index_screen._open_tag_button is None
        assert f"No titles found for tag: {tag.name}" in loguru_sink

    def test_the_sub_items_added_are_counted(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        group = next(iter(barks_reader.ui.main_index_screen.BARKS_TAG_GROUPS))
        main_index_screen._open_tag_item = IndexItem(group, group.value)
        layout = MagicMock()
        layout.children = [MagicMock()] * 3
        with (
            patch.object(main_index_screen, "_get_sub_item_layout", return_value=layout),
            patch.object(main_index_screen, "_insert_tag_sub_items_layout"),
        ):
            main_index_screen._add_sub_items(0)
        assert f"Index sub-items added under '{group.name}': 3." in loguru_sink
