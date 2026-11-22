"""The A-Z index of titles, tags and tag groups: its entries and what opens under them. Kivy-free.

The Main Index screen shows a letter page of these entries, and under a tag the titles it
tags (each at the pages the tag is on), under a tag group its tags.
"""

from __future__ import annotations

import string
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_PAGES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
    get_all_tags_in_tag_group,
    get_tag_titles,
)
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.speech_markup import escape_markup

from .index_headings import (
    SEE_REFERENCES,
    index_sort_key,
    tag_group_heading,
    tag_heading,
    tag_heading_markup,
    without_accents,
)
from .index_items import IndexItem
from .index_text import indexable_title
from .reader_formatter import get_display_title_str
from .reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from collections.abc import Iterable

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


# The letter pages there can be, in the order of the menu: what `index_letter` returns.
MAIN_INDEX_LETTERS: Final = "0" + string.ascii_uppercase


def index_letter(heading: str) -> str:
    """Return the letter page `heading` is listed on: its first letter, or "0" for a digit.

    An accented letter is listed under the plain one ("Éclair" under E), as the entity
    indexes list theirs.

    Args:
        heading: A title, tag or tag group as the index heads it.

    Returns:
        One of `MAIN_INDEX_LETTERS`.

    Raises:
        ValueError: If the heading is empty or starts with neither a letter nor a
            digit: there is no page to list it on.

    """
    first_letter = without_accents(heading[:1]).upper()[:1]
    if "0" <= first_letter <= "9":
        return "0"
    if not "A" <= first_letter <= "Z":
        msg = f'No index page for the heading "{heading}": it starts with no letter or digit.'
        raise ValueError(msg)
    return first_letter


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
        """Return the title as shown, with the group and tag it was found under.

        "Title (group/tag) ", and "(Title) (group/tag) " for a title Barks did not give.
        """
        assert self.title is not None
        title_str = get_display_title_str(self.title)

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
    # A title reached two ways is labelled by one rule, not by the page's sort order:
    # listed directly, it is the title alone; otherwise the first tag that leads to it.
    if type(item_id) is Titles:
        all_titles.add(item_id)
        hierarchies[item_id] = TitleHierarchy(None, None, item_id)
    elif type(item_id) is Tags:
        tag_titles = get_tag_titles(item_id)
        for title in tag_titles:
            hierarchies.setdefault(title, TitleHierarchy(parent_tag_group, item_id, title))
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


@dataclass(frozen=True, slots=True)
class SubIndexRow:
    """One row opened under a main index entry: what it stands for and how it reads.

    Attributes:
        item: What the row stands for and opens: a title at its tagged pages, or a tag.
        text: The row's text: a title with the tag's pages in it, or a tag's heading
            as markup.
        markup: Whether `text` is markup (a tag's heading).
        italic: Whether the row is a title, set in italics; a tag's row is bold.

    """

    item: IndexItem
    text: str
    markup: bool
    italic: bool


def sub_index_rows(item_id: Tags | TagGroups) -> list[SubIndexRow]:
    """Return the rows opened under a tag or a tag group of the main index.

    Args:
        item_id: The entry opened.

    Returns:
        Under a tag, the titles it tags in the order Barks submitted them, each
        opening at the tag's first page in it with all of them to step through;
        under a tag group, its tags by heading.

    """
    if type(item_id) is Tags:
        return [
            SubIndexRow(
                IndexItem(
                    id=title,
                    display_text=text,
                    page_to_goto=page,
                    tagged_pages=tagged_pages(item_id, title),
                ),
                text,
                markup=False,
                italic=True,
            )
            for title, page, text in tag_sub_items(item_id)
        ]
    assert isinstance(item_id, TagGroups)
    return [
        SubIndexRow(
            IndexItem(id=tag, display_text=text),
            tag_heading_markup(tag),
            markup=True,
            italic=False,
        )
        for tag, _page, text in tag_group_sub_items(item_id)
    ]
