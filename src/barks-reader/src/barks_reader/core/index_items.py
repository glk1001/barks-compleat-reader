"""What an index screen's row stands for, and what pressing it opens. Kivy-free."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM

if TYPE_CHECKING:
    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.entity_types import EntityType
    from barks_fantagraphics.whoosh_search_engine import TitleInfo


@dataclass(frozen=True, slots=True)
class IndexItem:
    id: str | Titles | Tags | TagGroups
    display_text: str
    page_to_goto: str = ""
    # The pages a title's row is about, which the title view steps through: a tag's, for
    # a title listed under a tag, or a speech index term's (see page_to_goto).
    tagged_pages: tuple[str, ...] = ()
    entity_type: EntityType | None = None  # None = plain word search; set for entity index items
    # A cross-reference's target heading: the row reads "<display_text>. See <see>".
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
        tagged_pages=tuple(page.comic_page for page in title_speech_info.fanta_pages.values()),
    )
