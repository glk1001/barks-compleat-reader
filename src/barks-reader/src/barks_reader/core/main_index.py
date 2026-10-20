"""The A-Z index of titles, tags and tag groups: its entries and what opens under them. Kivy-free.

The Main Index screen shows a letter page of these entries, and under a tag the titles it
tags (each at the pages the tag is on), under a tag group its tags.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_PAGES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
    get_all_tags_in_tag_group,
    get_tag_titles,
)
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import COVERS_SET
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.speech_markup import escape_markup

from .index_headings import (
    SEE_REFERENCES,
    index_sort_key,
    tag_group_heading,
    tag_heading,
    tag_heading_markup,
)
from .index_items import IndexItem
from .index_text import indexable_title
from .reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from collections.abc import Iterable

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


def index_letter(heading: str) -> str:
    """Return the letter page `heading` is listed on: its first letter, or "0" for a digit."""
    first_letter = heading[0].upper()
    assert ("0" <= first_letter <= "9") or ("A" <= first_letter <= "Z")
    return "0" if "0" <= first_letter <= "9" else first_letter


def index_item_markup(item: IndexItem) -> str:
    """Return a top-level row's text as markup: a cross-reference's "See" in italics."""
    if item.see:
        return f"{escape_markup(item.display_text)}. [i]See[/i] {escape_markup(item.see)}"
    if isinstance(item.id, Tags):
        return tag_heading_markup(item.id)
    return escape_markup(item.display_text)


def build_main_index() -> dict[str, list[IndexItem]]:
    """Return the index: every title, tag and tag group by its letter page, sorted.

    Individual covers ("Four Color #189 Cover", ...) are noise in an A-Z index and are
    left out: they are all reachable through the "All Covers" collection, which is not
    in COVERS_SET and so is still indexed. Tags are headed as an index heads them (see
    `index_headings`), and the other names a reader may look them up by are "See"
    cross-references.
    """
    index: dict[str, list[IndexItem]] = defaultdict(list)

    for title in Titles:
        if title in COVERS_SET:
            continue
        title_str = indexable_title(title)
        index[index_letter(title_str)].append(IndexItem(title, title_str))

    for tag in Tags:
        heading = tag_heading(tag)
        index[index_letter(heading)].append(IndexItem(tag, heading))
    for name, tag in SEE_REFERENCES.items():
        index[index_letter(name)].append(IndexItem(tag, name, see=tag_heading(tag)))

    for tag_group in TagGroups:
        heading = tag_group_heading(tag_group)
        index[index_letter(heading)].append(IndexItem(tag_group, heading))

    for items in index.values():
        items.sort(key=lambda item: index_sort_key(item.display_text))

    return index


@dataclass(frozen=True, slots=True)
class TitleHierarchy:
    """Where a letter page's title was found: directly, or under a tag (in a tag group)."""

    tag_group: TagGroups | None
    tag: Tags | None
    title: Titles | None

    def get_title_with_hierarchy(self) -> str:
        """Return the title, with the group and tag it was found under: "Title (group/tag) "."""
        assert self.title is not None
        title_str = ENUM_TO_STR_TITLE[self.title]

        if not self.tag_group and not self.tag:
            return title_str

        title_str += " ("
        if self.tag_group:
            title_str += self.tag_group.value + "/"
        if self.tag:
            title_str += self.tag.value
        title_str += ") "

        return title_str


def titles_for_letter(
    items: Iterable[IndexItem],
) -> tuple[list[FantaComicBookInfo], dict[Titles, TitleHierarchy]]:
    """Return every title a letter page's entries lead to, and where each was found.

    Args:
        items: The letter page's entries: titles, tags and tag groups.

    Returns:
        The titles' comic info, each title once, and each title's place in the hierarchy.

    """
    hierarchies: dict[Titles, TitleHierarchy] = {}
    all_titles: set[Titles] = set()

    for index_item in items:
        _collect_titles(index_item.id, all_titles, hierarchies)

    return [
        ALL_FANTA_COMIC_BOOK_INFO[title]
        for title in all_titles
        if title in ALL_FANTA_COMIC_BOOK_INFO
    ], hierarchies


def _collect_titles(
    item_id: str | Titles | Tags | TagGroups,
    all_titles: set[Titles],
    hierarchies: dict[Titles, TitleHierarchy],
    parent_tag_group: TagGroups | None = None,
) -> None:
    if type(item_id) is Titles:
        all_titles.add(item_id)
        hierarchies[item_id] = TitleHierarchy(None, None, item_id)
    elif type(item_id) is Tags:
        tag_titles = get_tag_titles(item_id)
        for title in tag_titles:
            hierarchies[title] = TitleHierarchy(parent_tag_group, item_id, title)
        all_titles.update(tag_titles)
    elif type(item_id) is TagGroups:
        for tag in BARKS_TAG_GROUPS[item_id]:
            if type(tag) is TagGroups:
                _collect_titles(tag, all_titles, hierarchies)
            else:
                _collect_titles(tag, all_titles, hierarchies, item_id)


def tagged_pages(item_id: Tags | TagGroups, sub_item_id: Titles | Tags) -> tuple[str, ...]:
    """Return a tag's pages in a title listed under it; none for a tag group's tags."""
    if not isinstance(item_id, Tags) or not isinstance(sub_item_id, Titles):
        return ()
    return tuple(BARKS_TAGGED_PAGES.get((item_id, sub_item_id), ()))


def tagged_title_with_page_nums(title: Titles, tag: Tags) -> tuple[str, str]:
    """Return the first page to goto, and the sortable title with page numbers."""
    if (tag, title) not in BARKS_TAGGED_PAGES:
        return "", indexable_title(title)

    page_nums = BARKS_TAGGED_PAGES[(tag, title)]

    title_str = indexable_title(title)
    page_nums_str = get_concat_page_nums_str(page_nums)

    return page_nums[0], title_str + ", " + page_nums_str


def tag_sub_items(tag: Tags) -> list[tuple[Titles, str, str]]:
    """Return the titles under a tag, in the order Barks submitted them: id, first page, text."""
    # In the order Barks submitted them: Titles is in that order.
    return [
        (title, *tagged_title_with_page_nums(title, tag))
        for title in sorted(BARKS_TAGGED_TITLES[tag])
    ]


def tag_group_sub_items(tag_group: TagGroups) -> list[tuple[Tags, str, str]]:
    """Return the tags under a tag group, by heading: id, no page, heading."""
    return sorted(
        ((tag, "", tag_heading(tag)) for tag in get_all_tags_in_tag_group(tag_group)),
        key=lambda t: index_sort_key(t[2]),
    )
