# ruff: noqa: SLF001

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.main_index_screen
import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET
from barks_reader.ui.index_screen import IndexItem
from barks_reader.ui.main_index_screen import MainIndexScreen, TitleHierarchy, reveal_distance
from kivy.clock import Clock

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence


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
        item = IndexItem(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, "My Title")

        with patch.object(barks_reader.ui.main_index_screen, "IndexItemButton") as mock_btn_cls:
            btn = main_index_screen._create_index_button(item)

            mock_btn_cls.assert_called_once()
            # Check args
            _, kwargs = mock_btn_cls.call_args
            assert kwargs["text"] == "My Title"
            assert btn is mock_btn_cls.return_value

    def test_a_cross_reference_row_reads_see_in_italics(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        item = IndexItem(Tags.GOLDIE_OGILT, "Glittering Goldie", see="O'Gilt, Goldie")
        with patch.object(barks_reader.ui.main_index_screen, "IndexItemButton") as mock_btn_cls:
            main_index_screen._create_index_button(item)
        _, kwargs = mock_btn_cls.call_args
        assert kwargs["text"] == "Glittering Goldie. [i]See[/i] O'Gilt, Goldie"
        assert kwargs["markup"] is True

    def test_tags_are_listed_by_their_index_headings(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        texts = {
            (item.id, item.display_text, item.see)
            for items in main_index_screen._item_index.values()
            for item in items
        }
        assert (Tags.FLINTHEART_GLOMGOLD, "Glomgold, Flintheart", "") in texts
        assert (Tags.DAISY, "Daisy Duck", "") in texts
        assert (Tags.FIRST_DAISY, "Daisy Duck: first appearance", "") in texts
        assert (Tags.GOLDIE_OGILT, "Glittering Goldie", "O'Gilt, Goldie") in texts
        assert (TagGroups.PIG_VILLAINS, "pig villains", "") in texts
        # Search shorthands are no longer index entries.
        assert not any(text == "Amnesia" for _, text, _ in texts)

    def test_a_letter_sorts_word_by_word_ignoring_punctuation(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        o_texts = [item.display_text for item in main_index_screen._item_index["O"]]
        assert o_texts.index("Officer of the Day") < o_texts.index("O'Gilt, Goldie")
        assert o_texts.index("O'Gilt, Goldie") < o_texts.index("Ohio")
        d_texts = [item.display_text for item in main_index_screen._item_index["D"]]
        assert d_texts.index("Daisy Duck") + 1 == d_texts.index("Daisy Duck: first appearance")

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
        main_index_screen._open_tag_button = MagicMock()
        layout = MagicMock()
        layout.children = [MagicMock()] * 3
        with (
            patch.object(main_index_screen, "_get_sub_item_layout", return_value=layout),
            patch.object(main_index_screen, "_insert_tag_sub_items_layout"),
            patch.object(main_index_screen, "_reveal_sub_items") as reveal,
        ):
            main_index_screen._add_sub_items(0)
        assert f"Index sub-items added under '{group.name}': 3." in loguru_sink
        reveal.assert_called_once_with(group, main_index_screen._open_tag_button, layout)

    @staticmethod
    def _opened_sub_item_ids(
        screen: MainIndexScreen, item_id: Tags | TagGroups, members: Sequence[Titles | Tags]
    ) -> list[Titles | Tags]:
        """Open `item_id`, listing `members`, and return its sub-items' ids, top to bottom."""
        screen._open_tag_item = IndexItem(item_id, "")
        screen._open_tag_button = MagicMock(padding=[0, 0, 0, 0])
        module = barks_reader.ui.main_index_screen
        with (
            patch.object(module, "BARKS_TAGGED_TITLES", {item_id: members}),
            patch.object(module, "get_all_tags_in_tag_group", return_value=set(members)),
            patch.object(module, "BoxLayout"),
            patch.object(module, "_MainIndexTitleItemButton"),
            patch.object(screen, "_get_tagged_title_with_page_nums", return_value=("", "")),
            patch.object(screen, "_get_tagged_pages", return_value=()),
            patch.object(module, "IndexItem") as index_item,
        ):
            screen._get_sub_item_layout(item_id)
        return [c.kwargs["id"] for c in index_item.call_args_list]

    def test_a_tags_titles_are_listed_in_the_order_barks_submitted_them(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        titles = [Titles.VICTORY_GARDEN_THE, Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]
        listed = self._opened_sub_item_ids(main_index_screen, Tags.AMNESIA_STORIES, titles)
        assert listed == sorted(titles)
        assert listed[0] == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD  # 1942, before 1943

    def test_a_tag_groups_tags_are_listed_by_heading(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        tags = [Tags.SOAPY_SLICK, Tags.P_J_MC_BRINE, Tags.MR_MC_SWINE]
        listed = self._opened_sub_item_ids(main_index_screen, TagGroups.PIG_VILLAINS, tags)
        assert listed == [Tags.P_J_MC_BRINE, Tags.MR_MC_SWINE, Tags.SOAPY_SLICK]

    def test_a_tag_group_with_no_tags_opens_nothing(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        group = TagGroups.AFRICA
        main_index_screen._open_tag_button = MagicMock()

        with (
            patch.object(barks_reader.ui.main_index_screen, "BARKS_TAG_GROUPS", {}),
            patch.object(Clock, "schedule_once") as schedule,
        ):
            main_index_screen._handle_tag_group(MagicMock(), IndexItem(group, group.value))

        schedule.assert_not_called()
        assert main_index_screen._open_tag_button is None
        assert f"No tags found for tag group: {group.name}" in loguru_sink


class TestTaggedTitleRows:
    """A title under a tag shows the pages the tag is on, and opens at the first."""

    def test_a_title_tagged_on_pages_shows_them_and_opens_at_the_first(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        pages = {(Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE): ["7", "8", "9", "12"]}
        with patch.object(barks_reader.ui.main_index_screen, "BARKS_TAGGED_PAGES", pages):
            row = main_index_screen._get_tagged_title_with_page_nums(
                Titles.BACK_TO_THE_KLONDIKE, Tags.ALASKA
            )
        assert row == ("7", "Back to the Klondike, 7-9,12")

    def test_a_title_tagged_as_a_whole_opens_at_its_start(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        with patch.object(barks_reader.ui.main_index_screen, "BARKS_TAGGED_PAGES", {}):
            row = main_index_screen._get_tagged_title_with_page_nums(
                Titles.BACK_TO_THE_KLONDIKE, Tags.ALASKA
            )
        assert row == ("", "Back to the Klondike")

    def test_a_title_under_a_tag_carries_all_the_tags_pages(self) -> None:
        pages = {(Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE): ["7", "8", "9", "12"]}
        with patch.object(barks_reader.ui.main_index_screen, "BARKS_TAGGED_PAGES", pages):
            assert MainIndexScreen._get_tagged_pages(Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE) == (
                "7",
                "8",
                "9",
                "12",
            )
            assert MainIndexScreen._get_tagged_pages(Tags.ALASKA, Titles.TRICK_OR_TREAT) == ()

    def test_a_tag_under_a_group_carries_no_pages(self) -> None:
        assert MainIndexScreen._get_tagged_pages(TagGroups.AFRICA, Tags.ALASKA) == ()


class TestTitleHierarchy:
    """A title found under a tag says where: "Title (group/tag) "."""

    def test_a_title_found_directly_is_just_its_title(self) -> None:
        hierarchy = TitleHierarchy(None, None, Titles.BACK_TO_THE_KLONDIKE)
        assert hierarchy.get_title_with_hierarchy() == "Back to the Klondike"

    def test_a_title_under_a_tag_in_a_group_names_both(self) -> None:
        hierarchy = TitleHierarchy(TagGroups.AFRICA, Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE)
        assert hierarchy.get_title_with_hierarchy() == (
            f"Back to the Klondike ({TagGroups.AFRICA.value}/{Tags.ALASKA.value}) "
        )

    def test_a_title_under_a_top_level_tag_names_the_tag(self) -> None:
        hierarchy = TitleHierarchy(None, Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE)
        assert hierarchy.get_title_with_hierarchy() == "Back to the Klondike (Alaska) "


class TestRevealSubItems:
    """Opened near the bottom of the view, a tag's sub-items are scrolled into it."""

    @pytest.mark.parametrize(
        ("items_bottom", "owner_top", "distance"),
        [
            (500, 900, 0),  # already in view: no scroll
            (-200, 400, 210),  # hidden below: up by that much, and the padding
            (-2000, 400, 600),  # taller than the view: the row goes to its top
        ],
    )
    def test_the_distance_shows_the_sub_items_but_keeps_their_row(
        self, items_bottom: float, owner_top: float, distance: float
    ) -> None:
        assert (
            reveal_distance(
                view_bottom=0,
                view_top=1000,
                items_bottom=items_bottom,
                owner_top=owner_top,
                padding=10,
            )
            == distance
        )

    @staticmethod
    def _scroll_view(*, pending: bool = False) -> MagicMock:
        """Return a scroll view over 0-1000 of 2000px of content, at its top."""
        content = MagicMock()
        content._trigger_layout.is_triggered = pending
        view = MagicMock(y=0, top=1000, scroll_y=1.0, children=[content])
        view.parent.to_widget = lambda x, y: (x, y)
        view.convert_distance_to_scroll = lambda dx, dy: (dx / 1000, dy / 1000)
        return view

    @staticmethod
    def _widget(y: float, top: float) -> MagicMock:
        widget = MagicMock(x=0, y=y, top=top)
        widget.to_window = lambda x, y: (x, y)
        widget._trigger_layout.is_triggered = False
        widget.parent._trigger_layout.is_triggered = False  # its column, laid out
        return widget

    def _reveal(self, screen: MainIndexScreen, view: MagicMock, sub_items: MagicMock) -> None:
        button = self._widget(y=30, top=55)
        with patch.object(MainIndexScreen, "ids", SimpleNamespace(index_scroll_view=view)):
            screen._reveal_sub_items(Tags.FLINTHEART_GLOMGOLD, button, sub_items)

    def test_sub_items_opened_below_the_view_are_scrolled_into_it(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        view = self._scroll_view()
        self._reveal(main_index_screen, view, self._widget(y=-300, top=30))
        assert view.scroll_y == pytest.approx(1.0 - 0.31)  # 300px, and 10 of padding
        assert "Index scrolled to show the sub-items under 'FLINTHEART_GLOMGOLD'." in loguru_sink

    def test_sub_items_already_in_view_move_nothing(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        view = self._scroll_view()
        self._reveal(main_index_screen, view, self._widget(y=200, top=500))
        assert view.scroll_y == 1.0
        assert not any("Index scrolled" in line for line in loguru_sink)

    def test_the_scroll_waits_until_the_layouts_have_placed_the_sub_items(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        view = self._scroll_view(pending=True)
        with patch.object(Clock, "schedule_once") as schedule:
            self._reveal(main_index_screen, view, self._widget(y=-300, top=30))
        schedule.assert_called_once()
        assert view.scroll_y == 1.0

    def test_sub_items_closed_again_meanwhile_move_nothing(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        view = self._scroll_view()
        sub_items = self._widget(y=-300, top=30)
        sub_items.parent = None
        self._reveal(main_index_screen, view, sub_items)
        assert view.scroll_y == 1.0
