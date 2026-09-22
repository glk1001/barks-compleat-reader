"""What the data says the app should show, derived the way the app derives it.

A GUI test that pins a number seen in one run ("7 pages", "2 results") is right
until the data changes. These ask the same core code the app uses - the title
lists, the comic layout builder, the search facade, the wiki join, the Reader
Files directories - so the expectation moves with the corpus. Each needs the
real data on this machine, which a GUI test needs to boot the app at all.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_search import ComicSearch, SearchMode
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_gui import harness
from barks_reader.core.comic_book_page_info import ComicLayoutBuilder
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.page_info_adapters import FantagraphicsPanelSegmentsAdapter
from barks_reader.core.system_file_paths import SystemFilePaths
from barks_reader.core.wiki_integration import wiki_page_for_title

if TYPE_CHECKING:
    from pathlib import Path

    from barks_reader.core.comic_book_page_info import ComicLayout

# The page image types the document reader shows (document_reader.IMAGE_EXTENSIONS,
# which is Kivy-side and so not importable here).
DOCUMENT_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


def is_title(name: str) -> bool:
    """Return whether `name` is a ``Titles`` member name, as the tree and goto lines log."""
    return name in Titles.__members__


@cache
def chrono_range_titles(start: int, end: int) -> list[str]:
    """Return the ``Titles`` names of a chronological year-range node, in tree order.

    The tree spec concatenates the year lists of the range (tree_spec
    ``_year_range_titles``), and a title row logs its ``Titles`` name.
    """
    lists = FilteredTitleLists().get_title_lists()
    return [
        info.comic_book_info.title.name
        for year in range(start, end + 1)
        for info in lists[str(year)]
    ]


@cache
def system_paths() -> SystemFilePaths:
    """Return the app's Reader Files paths, rooted where a dev run roots them."""
    data_dir = harness.app_data_dir()
    if data_dir is None:
        msg = "no app data directory: BARKS_READER_DATA_DIR is not set and .env.runtime has none"
        raise RuntimeError(msg)
    paths = SystemFilePaths()
    paths.set_barks_reader_files_dir(data_dir / "Reader Files", check_files=False)
    return paths


@cache
def comics_database() -> ComicsDatabase:
    """Return the comics database, as the app builds it."""
    return ComicsDatabase(for_building_comics=False)


@cache
def comic_layout(title: str) -> ComicLayout:
    """Return the page layout the reader builds for `title` (its display title).

    Built with the same builder and adapter as the app, so the page map (and
    with it the last page index and the last body page) is the app's own.
    """
    database = comics_database()
    adapter = FantagraphicsPanelSegmentsAdapter(
        database, system_paths().get_barks_reader_fantagraphics_panel_segments_root_dir()
    )
    return ComicLayoutBuilder(sorted_pages_port=adapter).build(database.get_comic_book(title))


def last_page_index(title: str, *, two_up: bool = False) -> int:
    """Return the index the reader's goto-end lands on for `title`.

    Two-up, the reader shows units (a solo page or a pair) and stands on a
    unit's left page, so the end is the last unit's left page.
    """
    layout = comic_layout(title)
    if two_up:
        return layout.display_units[-1].left_page_index
    return len(layout.page_map) - 1


def unit_starts(title: str) -> list[int]:
    """Return the left page index of each unit the reader shows two-up, in order."""
    return [unit.left_page_index for unit in comic_layout(title).display_units]


def unit_start(title: str, page_index: int) -> int:
    """Return the page the reader shows two-up when asked for `page_index`: its unit's left."""
    layout = comic_layout(title)
    unit_idx = layout.unit_idx_for(page_index)
    if unit_idx is None:
        msg = f"no page index {page_index} in {title!r}"
        raise ValueError(msg)
    return layout.display_units[unit_idx].left_page_index


def document_page_count(doc_dir: Path) -> int:
    """Return how many pages the document reader opens `doc_dir` with."""
    return sum(1 for p in doc_dir.iterdir() if p.suffix.lower() in DOCUMENT_IMAGE_SUFFIXES)


def intro_document_dir() -> Path:
    """Return the directory of the reader's introduction document."""
    return system_paths().get_intro_doc_dir()


def censorship_document_dir() -> Path:
    """Return the directory of the censorship fixes document."""
    return system_paths().get_censorship_fixes_doc_dir()


@cache
def title_search_count(query: str) -> int:
    """Return how many titles the search screen lists for `query`."""
    search = ComicSearch(system_paths().get_barks_reader_indexes_dir())
    return len(search.search(query, SearchMode.TITLE).title_strings)


def wiki_page(bundle: Path, title: Titles) -> Path | None:
    """Return the wiki story page a title's chip opens, or None if the bundle lacks it."""
    return wiki_page_for_title(bundle, title)
