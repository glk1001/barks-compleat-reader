"""A speech search's hits as the rows a results list shows: title, pages, count. Kivy-free.

The word search and the Words index list the same thing, the stories a term is said
in with the pages it is said on, and build their rows here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from .index_text import sortable_string
from .reader_formatter import get_fitted_title_with_page_nums

if TYPE_CHECKING:
    from barks_fantagraphics.whoosh_search_engine import TitleInfo

# The longest a word search's row is: title, pages and hit count together.
MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN = 50


def comic_pages(title_speech_info: TitleInfo) -> tuple[str, ...]:
    """Return the pages a term is found on in a story, as the comic numbers them."""
    return tuple(page.comic_page for page in title_speech_info.fanta_pages.values())


class SpeechHitRow(NamedTuple):
    """One story a term is found in, as its row: where it opens, what it reads, its hits."""

    title_str: str
    first_page: str
    text: str
    info: TitleInfo


def speech_hit_rows(
    found: dict[str, TitleInfo],
    *,
    max_len: int,
    hit_counts: dict[str, int] | None = None,
    sortable: bool = False,
) -> list[SpeechHitRow]:
    """Return each found story's row, sorted by its text.

    Args:
        found: The stories found, by title, each with the pages the term is on.
        max_len: The longest a row's text may be, title and pages together, before the
            pages are cut short.
        hit_counts: A typed query's count of matching bubbles per story; given, each
            row ends in its story's: "Lost in the Andes!, 3,5 (4)".
        sortable: Whether the title lists as an index does, a leading "The" or "A"
            moved to its end, before the pages.

    Returns:
        The rows, in text order.

    """
    rows: list[SpeechHitRow] = []
    for title_str, info in found.items():
        count = "" if hit_counts is None else f" ({hit_counts.get(title_str, 0)})"
        room = max_len - len(count)
        pages = list(comic_pages(info))
        # The article moves before the row is fitted, so it stays with the title:
        # "Apple Tree, The, 1". Moved after, it trailed the pages: "Apple Tree, 1, The".
        listed_title = sortable_string(title_str) if sortable else title_str
        first_page, text = get_fitted_title_with_page_nums(listed_title, pages, room)
        if listed_title != title_str and not text.startswith(listed_title):
            # No room for the whole title: its article goes before any of its words.
            bare_title = listed_title.rsplit(", ", 1)[0]
            first_page, text = get_fitted_title_with_page_nums(bare_title, pages, room)
        rows.append(SpeechHitRow(title_str, first_page, text + count, info))
    rows.sort(key=lambda row: row.text)
    return rows
