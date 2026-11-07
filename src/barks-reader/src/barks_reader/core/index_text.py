"""How the index screens write a title or tag: sorted by its word after "The" or "A".

Kivy-free, so the GUI tests can tell which index entries are titles by the text the
index shows, rather than by knowing its layout.
"""

from __future__ import annotations

import textwrap

from barks_fantagraphics.alpha_split import bucket_label_parts
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles

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
    return sortable_string(_shortened(title_str, MAX_TITLE_AND_PAGES_LEN))


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
    return _shortened(text, INDEX_ITEM_MAX_TEXT_WIDTH)


_ELLIPSIS = "..."


def _shortened(text: str, width: int) -> str:
    """Return `text` cut at a word to `width`, with an ellipsis; mid-word if it must be.

    `textwrap.shorten` drops a first word longer than `width` whole, leaving just the
    ellipsis ("500,000,000,...,000" showed as "..."), so that word is cut instead.
    """
    shortened = textwrap.shorten(text, width=width, placeholder=_ELLIPSIS)
    if shortened != _ELLIPSIS or not text.strip():
        return shortened
    return " ".join(text.split())[: width - len(_ELLIPSIS)].rstrip() + _ELLIPSIS


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
