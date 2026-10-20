"""What an index screen's row stands for, and what pressing it opens. Kivy-free."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM

from .index_text import shorten_if_necessary
from .speech_hits import comic_pages

if TYPE_CHECKING:
    from collections.abc import Iterable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.entity_types import EntityType
    from barks_fantagraphics.whoosh_search_engine import TitleInfo


@dataclass(frozen=True, slots=True)
class IndexItem:
    """One row of an index: what it stands for, its text, and the page it opens at.

    Attributes:
        id: What the row stands for: a title, a tag, a tag group, or a term's string.
        display_text: The row's text.
        page_to_goto: The page a title's row opens the comic at, or "" for the front.
        tagged_pages: The pages a title's row is about, which the title view steps
            through: a tag's, for a title listed under a tag, or a speech index term's.
        entity_type: The entity index the row belongs to; None for a plain word search.
        see: A cross-reference's target heading: the row reads "<display_text>. See <see>".

    """

    id: str | Titles | Tags | TagGroups
    display_text: str
    page_to_goto: str = ""
    tagged_pages: tuple[str, ...] = ()
    entity_type: EntityType | None = None
    see: str = ""


def title_row_item(
    title_str: str, first_page: str, display_text: str, title_speech_info: TitleInfo
) -> IndexItem:
    """Return the index item a term's title row opens: at its first page, with all of them.

    Every page the row lists goes with it, so the title view steps through them all
    (as a tag's), not just the first.

    Args:
        title_str: The title's canonical string.
        first_page: The page the row opens at.
        display_text: The row's text.
        title_speech_info: The term's hits in the title, one per page.

    Returns:
        The row's item, with every page listed as its tagged pages.

    """
    return IndexItem(
        id=STR_TITLE_TO_ENUM[title_str],
        display_text=display_text,
        page_to_goto=first_page,
        tagged_pages=comic_pages(title_speech_info),
    )


def entity_index(terms: Iterable[str]) -> dict[str, list[IndexItem]]:
    """Return an entity index's rows, grouped under the letter each term starts with.

    There are few enough names or places per letter to list them directly, so the
    index is flat: no prefix level between the letter and the rows.

    Args:
        terms: The entity terms, in the order their rows are listed.

    Returns:
        The rows under each letter (``"A"`` to ``"Z"``), in the terms' order. An empty
        term is left out.

    Raises:
        RuntimeError: A term starts with something other than a letter.

    """
    index: dict[str, list[IndexItem]] = defaultdict(list)
    for term in terms:
        if not term:
            continue
        ch = term[0].lower()
        if not "a" <= ch <= "z":
            msg = f'Entity term has non-alpha prefix: "{term}".'
            raise RuntimeError(msg)
        index[ch.upper()].append(IndexItem(term, shorten_if_necessary(term)))
    return index
