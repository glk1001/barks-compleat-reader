"""How the index screens write a title or tag: sorted by its word after "The" or "A".

Kivy-free, so the GUI tests can tell which index entries are titles by the text the
index shows, rather than by knowing its layout.
"""

from __future__ import annotations

import textwrap

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
    text_upper = text.upper()
    if text_upper.startswith("THE "):
        return text[4:] + ", The"
    if text_upper.startswith("A "):
        return text[2:] + ", A"
    return text


def indexable_title_from_str(title_str: str) -> str:
    """Return a title as an index row shows it: shortened to fit, then made sortable."""
    return sortable_string(
        textwrap.shorten(title_str, width=MAX_TITLE_AND_PAGES_LEN, placeholder="...")
    )


def indexable_title(title: Titles) -> str:
    """Return `title` as an index row shows it."""
    return indexable_title_from_str(ENUM_TO_STR_TITLE[title])
