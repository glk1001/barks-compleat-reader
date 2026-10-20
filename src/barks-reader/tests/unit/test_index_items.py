"""What an index row opens (barks_reader.core.index_items)."""

from __future__ import annotations

from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.index_items import title_row_item


def test_a_title_row_opens_at_its_first_page_with_every_page_it_lists() -> None:
    """The title view steps through all of a term's pages, as a tag's, not just the first."""
    pages = {f"fanta-{p}": MagicMock(comic_page=p) for p in ("3", "4", "5", "12")}
    item = title_row_item(
        "Donald Duck Finds Pirate Gold", "3", "Pirate Gold, 3-5,12", MagicMock(fanta_pages=pages)
    )
    assert item.id == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
    assert item.page_to_goto == "3"
    assert item.tagged_pages == ("3", "4", "5", "12")
