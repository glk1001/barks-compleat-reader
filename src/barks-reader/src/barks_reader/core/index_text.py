"""How the index screens write a title or tag: sorted by its word after "The" or "A".

Kivy-free, so the GUI tests can tell which index entries are titles by the text the
index shows, rather than by knowing its layout.
"""

from __future__ import annotations

import re
import textwrap
from typing import TYPE_CHECKING

from barks_fantagraphics.alpha_split import bucket_label_parts
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles

if TYPE_CHECKING:
    from collections.abc import Callable

# The longest title an index row shows with its pages, before it is shortened.
MAX_TITLE_AND_PAGES_LEN = 34 + 8  # len(", 11,...") == 8


def sortable_string(text: str) -> str:
    """Return `text` with a leading "The" or "A" moved to the end: "Ghost of the Grotto, The".

    Args:
        text: A title or tag name.

    Returns:
        The text as the index lists it, so it sorts by its first real word.

    """
    # The article keeps its case: "THE END" lists as "END, THE".
    text_upper = text.upper()
    if text_upper.startswith("THE "):
        return f"{text[4:]}, {text[:3]}"
    if text_upper.startswith("A "):
        return f"{text[2:]}, {text[:1]}"
    return text


def indexable_title_from_str(title_str: str) -> str:
    """Return a title as an index row shows it: shortened to fit, then made sortable."""
    return sortable_string(shortened_at_a_word(title_str, MAX_TITLE_AND_PAGES_LEN))


def indexable_title(title: Titles) -> str:
    """Return `title` as an index row shows it."""
    return indexable_title_from_str(ENUM_TO_STR_TITLE[title])


# The longest text a word or entity index item shows, before it is shortened.
INDEX_ITEM_MAX_TEXT_WIDTH = 30
# The zeros in the one huge number said in a story ("500,000,000,...,000.16"): any
# other number starting "500,000" is an ordinary term, shortened like the rest.
_HUGE_NUMBER_ZEROS = 69 + 8


def shorten_if_necessary(text: str) -> str:
    """Return an index item's text, shortened at a word to fit its row.

    Args:
        text: A term the index lists.

    Returns:
        The text, cut with an ellipsis when it is too long for a row; the one
        77-zero number said in a story is written out in words instead.

    """
    if text.startswith("500,000") and text.count("0") == _HUGE_NUMBER_ZEROS:
        return "500,000,—plus sixty-nine more zeroes—,000.16"

    if len(text) <= INDEX_ITEM_MAX_TEXT_WIDTH:
        return text
    return shortened_at_a_word(text, INDEX_ITEM_MAX_TEXT_WIDTH)


_ELLIPSIS = "..."


def shortened_at_a_word(text: str, width: int, ellipsis: str = _ELLIPSIS) -> str:
    """Return `text` cut at a word to `width`, with an ellipsis; mid-word if it must be.

    `textwrap.shorten` drops a first word longer than `width` whole, leaving just the
    ellipsis ("500,000,000,...,000" showed as "..."), so that word is cut instead.

    Args:
        text: The text, its runs of whitespace taken as one space.
        width: The most characters to return, the ellipsis among them.
        ellipsis: What marks the cut.

    Returns:
        The text whole if it fits, else as many of its words as do and the ellipsis.

    """
    shortened = textwrap.shorten(text, width=width, placeholder=ellipsis)
    if shortened != ellipsis or not text.strip():
        return shortened
    return " ".join(text.split())[: width - len(ellipsis)].rstrip() + ellipsis


def stacked_prefix_label(prefix: str, terms: list[str]) -> str:
    """Return the prefix button's display text, with the range stacked over two lines.

    Twenty buttons share the bar's width, so "sho-shy" on one line only fits at a size
    that is hard to read. Stacked, each line is at most three characters and the label
    can render at nearly the A-Z menu's size.

    Args:
        prefix: The bucket's canonical label, as used everywhere else as its key.
        terms: The bucket's terms, in display order.

    Returns:
        The two ends of the range separated by a newline, or ``prefix`` unchanged when
        the bucket has a single-prefix label or its ends no longer rejoin to ``prefix``.

    """
    start, end = bucket_label_parts(terms)
    if start == end or f"{start}-{end}" != prefix:
        return prefix
    return f"{start}\n{end}"


# In a title row's text, where its page numbers start: the title before them gives way.
_PAGES_START = re.compile(r", \d")
_ROW_ELLIPSIS = "\u2026"


def shortened_keeping_pages(full: str, fits: Callable[[str], bool]) -> str:
    """Return a title row's text cut to fit its row, its page numbers kept.

    The title gives way, not the pages after it: "Lost in the An…, 3-5,12". As much
    of the title is kept as fits, found by halving, on the footing that a longer
    text never fits where a shorter one does not.

    Args:
        full: The row's whole text, "Title, pages", or a title alone.
        fits: Whether a text fits the row, as its font draws it.

    Returns:
        The whole text when it fits; else the longest start of the title that fits
        with an ellipsis and the pages after it, which is the ellipsis and the pages
        alone when no start does.

    """
    if fits(full):
        return full
    pages_at = _PAGES_START.search(full)
    title, pages = (full[: pages_at.start()], full[pages_at.start() :]) if pages_at else (full, "")
    low, high = 0, len(title)
    while low < high:
        keep = (low + high + 1) // 2
        if fits(f"{title[:keep].rstrip()}{_ROW_ELLIPSIS}{pages}"):
            low = keep
        else:
            high = keep - 1
    return f"{title[:low].rstrip()}{_ROW_ELLIPSIS}{pages}"
