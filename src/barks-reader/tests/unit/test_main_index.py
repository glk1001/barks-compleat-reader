"""The A-Z index of titles, tags and tag groups (barks_reader.core.main_index)."""

from __future__ import annotations

from unittest.mock import patch

import barks_reader.core.main_index
import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET
from barks_reader.core.index_items import IndexItem
from barks_reader.core.main_index import (
    TitleHierarchy,
    build_main_index,
    index_item_markup,
    index_letter,
    tag_group_sub_items,
    tag_sub_items,
    tagged_pages,
    tagged_title_with_page_nums,
    titles_for_letter,
)


@pytest.fixture(scope="module")
def index() -> dict[str, list[IndexItem]]:
    return build_main_index()


class TestBuildMainIndex:
    def test_build_index_excludes_individual_covers(
        self, index: dict[str, list[IndexItem]]
    ) -> None:
        indexed_ids = {item.id for items in index.values() for item in items}
        assert not (indexed_ids & COVERS_SET)
        assert Titles.ALL_COVERS in indexed_ids
        assert Titles.DONALD_DUCK_FINDS_PIRATE_GOLD in indexed_ids

    def test_tags_are_listed_by_their_index_headings(
        self, index: dict[str, list[IndexItem]]
    ) -> None:
        texts = {
            (item.id, item.display_text, item.see) for items in index.values() for item in items
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
        self, index: dict[str, list[IndexItem]]
    ) -> None:
        o_texts = [item.display_text for item in index["O"]]
        assert o_texts.index("Officer of the Day") < o_texts.index("O'Gilt, Goldie")
        assert o_texts.index("O'Gilt, Goldie") < o_texts.index("Ohio")
        d_texts = [item.display_text for item in index["D"]]
        assert d_texts.index("Daisy Duck") + 1 == d_texts.index("Daisy Duck: first appearance")

    def test_a_digit_heading_lists_on_the_0_page(self) -> None:
        assert (index_letter("313"), index_letter("alaska")) == ("0", "A")

    def test_a_cross_reference_row_reads_see_in_italics(self) -> None:
        item = IndexItem(Tags.GOLDIE_OGILT, "Glittering Goldie", see="O'Gilt, Goldie")
        assert index_item_markup(item) == "Glittering Goldie. [i]See[/i] O'Gilt, Goldie"
        assert index_item_markup(IndexItem("Donald & co", "Donald & co")) == "Donald &amp; co"


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


class TestTitlesForLetter:
    def test_a_titles_entry_is_found_directly_and_a_tags_under_the_tag(self) -> None:
        items = [
            IndexItem(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, "Donald Duck Finds Pirate Gold"),
            IndexItem(Tags.ALASKA, "Alaska"),
        ]
        infos, hierarchies = titles_for_letter(items)
        titles = {info.comic_book_info.title for info in infos}
        assert {Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, Titles.BACK_TO_THE_KLONDIKE} <= titles
        assert len(infos) == len(titles)  # each title once
        assert hierarchies[Titles.DONALD_DUCK_FINDS_PIRATE_GOLD] == TitleHierarchy(
            None, None, Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        )
        assert hierarchies[Titles.BACK_TO_THE_KLONDIKE] == TitleHierarchy(
            None, Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE
        )

    def test_a_tag_groups_titles_name_the_group(self) -> None:
        _, hierarchies = titles_for_letter([IndexItem(TagGroups.PIG_VILLAINS, "pig villains")])
        assert hierarchies
        assert all(h.tag_group is TagGroups.PIG_VILLAINS for h in hierarchies.values())


class TestSubItems:
    def test_a_tags_titles_are_listed_in_the_order_barks_submitted_them(self) -> None:
        titles = [Titles.VICTORY_GARDEN_THE, Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]
        with patch.object(
            barks_reader.core.main_index, "BARKS_TAGGED_TITLES", {Tags.AMNESIA_STORIES: titles}
        ):
            listed = [t for t, _page, _text in tag_sub_items(Tags.AMNESIA_STORIES)]
        assert listed == sorted(titles)
        assert listed[0] == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD  # 1942, before 1943

    def test_a_tag_groups_tags_are_listed_by_heading(self) -> None:
        tags = [Tags.SOAPY_SLICK, Tags.P_J_MC_BRINE, Tags.MR_MC_SWINE]
        with patch.object(
            barks_reader.core.main_index, "get_all_tags_in_tag_group", return_value=set(tags)
        ):
            listed = [t for t, _page, _text in tag_group_sub_items(TagGroups.PIG_VILLAINS)]
        assert listed == [Tags.P_J_MC_BRINE, Tags.MR_MC_SWINE, Tags.SOAPY_SLICK]


class TestTaggedTitleRows:
    """A title under a tag shows the pages the tag is on, and opens at the first."""

    def test_a_title_tagged_on_pages_shows_them_and_opens_at_the_first(
        self,
    ) -> None:
        pages = {(Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE): ["7", "8", "9", "12"]}
        with patch.object(barks_reader.core.main_index, "BARKS_TAGGED_PAGES", pages):
            row = tagged_title_with_page_nums(Titles.BACK_TO_THE_KLONDIKE, Tags.ALASKA)
        assert row == ("7", "Back to the Klondike, 7-9,12")

    def test_a_title_tagged_as_a_whole_opens_at_its_start(
        self,
    ) -> None:
        with patch.object(barks_reader.core.main_index, "BARKS_TAGGED_PAGES", {}):
            row = tagged_title_with_page_nums(Titles.BACK_TO_THE_KLONDIKE, Tags.ALASKA)
        assert row == ("", "Back to the Klondike")

    def test_a_title_under_a_tag_carries_all_the_tags_pages(self) -> None:
        pages = {(Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE): ["7", "8", "9", "12"]}
        with patch.object(barks_reader.core.main_index, "BARKS_TAGGED_PAGES", pages):
            assert tagged_pages(Tags.ALASKA, Titles.BACK_TO_THE_KLONDIKE) == (
                "7",
                "8",
                "9",
                "12",
            )
            assert tagged_pages(Tags.ALASKA, Titles.TRICK_OR_TREAT) == ()

    def test_a_tag_under_a_group_carries_no_pages(self) -> None:
        assert tagged_pages(TagGroups.AFRICA, Tags.ALASKA) == ()
