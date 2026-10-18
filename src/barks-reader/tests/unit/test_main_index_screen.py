# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.index_screen
import barks_reader.ui.main_index_screen
import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET
from barks_reader.ui.index_screen import IndexItem
from barks_reader.ui.main_index_screen import MainIndexScreen, TitleHierarchy
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
            screen._open_tag_widgets = []
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
        # The names a reader looks the leads up by stay findable, as cross-references.
        scrooge = "Uncle Scrooge: outside the Uncle Scrooge series"
        assert (Tags.SCROOGE_NOT_IN_US, "Scrooge", scrooge) in texts
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
        ):
            main_index_screen._add_sub_items(0)
        assert f"Index sub-items added under '{group.name}': 3." in loguru_sink

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


class TestSeeReferences:
    """A "See" cross-reference goes to its target's entry, on its letter page, and opens it."""

    @staticmethod
    def _page_with(screen: MainIndexScreen, entries: dict) -> MagicMock:
        """Return an on_letter_press stand-in that shows a page holding `entries`."""

        def show_page(_letter_button: object) -> None:
            screen._tag_entries.clear()
            screen._tag_entries.update(entries)

        return MagicMock(side_effect=show_page)

    def test_a_cross_reference_opens_its_target_on_its_letter_page(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        target_button = MagicMock()
        target_item = IndexItem(Tags.BLACK_PETE, "Black Pete")
        page = self._page_with(main_index_screen, {Tags.BLACK_PETE: (target_button, target_item)})
        letters = {"B": MagicMock(name="B")}
        see = IndexItem(Tags.BLACK_PETE, "Pete", see="Black Pete")
        with (
            patch.object(main_index_screen, "on_letter_press", page),
            patch.object(main_index_screen, "_alphabet_buttons", letters, create=True),
            patch.object(main_index_screen, "_hand_focus_to") as hand_focus,
            patch.object(main_index_screen, "_on_index_item_press") as press,
        ):
            assert main_index_screen._handle_terminal_item(MagicMock(), see) is True
        page.assert_called_once_with(letters["B"])
        hand_focus.assert_called_once_with(target_button)
        press.assert_called_once_with(target_button, target_item)
        assert 'Following "Pete" to "Black Pete".' in loguru_sink

    def test_a_digit_heading_is_on_the_0_page(self, main_index_screen: MainIndexScreen) -> None:
        page = self._page_with(main_index_screen, {})
        letters = {"0": MagicMock(name="0")}
        see = IndexItem(Tags.CAR_313, "car 313", see="313")
        with (
            patch.object(main_index_screen, "on_letter_press", page),
            patch.object(main_index_screen, "_alphabet_buttons", letters, create=True),
        ):
            main_index_screen._follow_see_reference(see)
        page.assert_called_once_with(letters["0"])

    def test_a_target_not_on_the_page_is_reported_and_nothing_opens(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        page = self._page_with(main_index_screen, {})
        see = IndexItem(Tags.BLACK_PETE, "Pete", see="Black Pete")
        with (
            patch.object(main_index_screen, "on_letter_press", page),
            patch.object(main_index_screen, "_alphabet_buttons", {"B": MagicMock()}, create=True),
            patch.object(main_index_screen, "_on_index_item_press") as press,
        ):
            main_index_screen._follow_see_reference(see)
        press.assert_not_called()
        assert 'No entry "Black Pete" for the cross-reference "Pete".' in loguru_sink

    @staticmethod
    def _letter_buttons(*letters: str) -> dict[str, MagicMock]:
        buttons = {}
        for letter in letters:
            buttons[letter] = MagicMock(name=letter)
            buttons[letter].text = letter
        return buttons

    def test_a_target_on_another_page_is_found_through_the_real_letter_press(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        """The letter press rebuilds the page's entries; the target is one of the new ones."""
        screen = main_index_screen
        letters = self._letter_buttons("B", "P")
        screen._selected_letter_button = letters["P"]
        screen._nav_active = False
        screen._tag_entries[Tags.BLACK_PETE] = (
            MagicMock(name="stale"),
            IndexItem(Tags.BLACK_PETE, "?"),
        )

        def populate(letter: str) -> None:
            for item in screen._get_items_for_letter(letter):
                screen._create_index_button(item)

        with (
            patch.object(screen, "_alphabet_buttons", letters, create=True),
            patch.object(screen, "_populate_index_grid", side_effect=populate),
            patch.object(barks_reader.ui.main_index_screen, "IndexItemButton"),
            patch.object(screen, "_handle_tag") as handle_tag,
        ):
            screen._follow_see_reference(IndexItem(Tags.BLACK_PETE, "Pete", see="Black Pete"))

        assert screen._selected_letter_button is letters["B"]
        target_button, target_item = screen._tag_entries[Tags.BLACK_PETE]
        assert target_item == IndexItem(Tags.BLACK_PETE, "Black Pete")
        handle_tag.assert_called_once_with(target_button, target_item)

    def test_a_target_on_the_shown_page_is_opened_in_place(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        """No letter press: it would close every open tag and scroll back to the top."""
        screen = main_index_screen
        screen._selected_letter_button = self._letter_buttons("G")["G"]
        target_button, target_item = MagicMock(), IndexItem(Tags.GYRO_GEARLOOSE, "Gyro Gearloose")
        screen._tag_entries[Tags.GYRO_GEARLOOSE] = (target_button, target_item)
        with (
            patch.object(screen, "on_letter_press") as letter_press,
            patch.object(screen, "_hand_focus_to") as hand_focus,
            patch.object(screen, "_on_index_item_press") as press,
        ):
            screen._follow_see_reference(
                IndexItem(Tags.GYRO_GEARLOOSE, "Gearloose", see="Gyro Gearloose")
            )
        letter_press.assert_not_called()
        hand_focus.assert_called_once_with(target_button)
        press.assert_called_once_with(target_button, target_item)

    def test_a_target_already_open_stays_open(
        self, main_index_screen: MainIndexScreen, loguru_sink: list[str]
    ) -> None:
        """A press on an open entry closes it: the cross-reference must not."""
        screen = main_index_screen
        screen._selected_letter_button = self._letter_buttons("G")["G"]
        target_button, target_item = MagicMock(), IndexItem(Tags.GYRO_GEARLOOSE, "Gyro Gearloose")
        screen._tag_entries[Tags.GYRO_GEARLOOSE] = (target_button, target_item)
        screen._open_tag_widgets = [MagicMock(owner_button=target_button)]
        with (
            patch.object(screen, "_hand_focus_to") as hand_focus,
            patch.object(screen, "_on_index_item_press") as press,
        ):
            screen._follow_see_reference(
                IndexItem(Tags.GYRO_GEARLOOSE, "Gearloose", see="Gyro Gearloose")
            )
        hand_focus.assert_called_once_with(target_button)
        press.assert_not_called()
        assert '"Gyro Gearloose" is open already.' in loguru_sink

    def test_every_tag_row_on_a_page_is_remembered_but_no_cross_reference(
        self, main_index_screen: MainIndexScreen
    ) -> None:
        tag_item = IndexItem(Tags.BLACK_PETE, "Black Pete")
        see_item = IndexItem(Tags.BLACK_PETE, "Pete", see="Black Pete")
        with patch.object(barks_reader.ui.main_index_screen, "IndexItemButton"):
            tag_button = main_index_screen._create_index_button(tag_item)
            main_index_screen._create_index_button(see_item)
        assert main_index_screen._tag_entries == {Tags.BLACK_PETE: (tag_button, tag_item)}
