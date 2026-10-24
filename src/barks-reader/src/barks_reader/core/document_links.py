"""Story links beside a document page: the comics its figures come from.

A document page image may have a JSON file of the same stem beside it (``page-007.png`` and
``page-007.json``) naming the stories its figures are taken from, so the document reader can
offer to open one at the page shown. The barks-wiki illustrated history writes them
(``barks-wiki/scripts/history_reader.py``)::

    {"figures": [{"figure": 5, "title": "MAHARAJAH_DONALD", "display_title": "Maharajah Donald",
                  "page": "2", "panels": [3], "box": [140, 1210, 1840, 1265]}]}

``title`` is a ``Titles`` member name and ``page`` a display page number. ``display_title``,
``panels`` and ``box`` are not read: the label is built from our own title info, so an assigned
title shows in parentheses as everywhere else. A page with no file, or a file that cannot be
read, has no links; an entry naming no known title, or a title with no Fantagraphics volume, is
skipped with a warning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import get_fanta_info
from loguru import logger

from . import log_markers

if TYPE_CHECKING:
    from pathlib import Path

LINKS_EXT = ".json"


@dataclass(frozen=True, slots=True)
class StoryLink:
    """One figure's story, and the page of it the figure shows."""

    title: Titles
    page: str
    label: str  # e.g. "Fig. 5: Maharajah Donald, page 2"


def load_story_links(page_path: Path) -> list[StoryLink]:
    """Return the story links for a document page, in the order its figures fall.

    Args:
        page_path: The page image.

    Returns:
        The links; none when the page has no links file or it cannot be read.

    """
    links_path = page_path.with_suffix(LINKS_EXT)
    if not links_path.is_file():
        return []
    try:
        figures = json.loads(links_path.read_text(encoding="utf-8"))["figures"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning(log_markers.DOCUMENT_LINKS_UNREADABLE.format(path=links_path, error=e))
        return []

    links = []
    for figure in figures:
        try:
            title = Titles[figure["title"]]
            page = str(figure["page"])
            number = int(figure["figure"])
        except (KeyError, TypeError, ValueError):
            logger.warning(log_markers.DOCUMENT_LINK_SKIPPED.format(path=links_path, entry=figure))
            continue
        fanta_info = get_fanta_info(title)
        if fanta_info is None:
            logger.warning(log_markers.DOCUMENT_LINK_SKIPPED.format(path=links_path, entry=figure))
            continue
        label = f"Fig. {number}: {fanta_info.comic_book_info.get_display_title()}, page {page}"
        links.append(StoryLink(title, page, label))
    return links
