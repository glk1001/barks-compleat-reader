from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.pages import get_sorted_srce_and_dest_pages_with_dimensions
from comic_utils.comic_consts import JSON_FILE_EXT

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.comic_book import ComicBook
    from barks_fantagraphics.comics_database import ComicsDatabase
    from barks_fantagraphics.page_classes import RequiredDimensions, SrceAndDestPages


class FantagraphicsPanelSegmentsAdapter:
    """Satisfies both ``SortedPagesPort`` and ``RequiredDimensionsPort``.

    Caches the result of the fantagraphics sorted-pages helper per comic so the
    two port methods, called in sequence by ``ComicLayoutBuilder.build()``, only
    trigger one round of panel-segment JSON I/O.
    """

    def __init__(
        self,
        comics_database: ComicsDatabase,
        panel_segments_root_dir: Path,
    ) -> None:
        self._comics_database = comics_database
        self._panel_segments_root_dir = panel_segments_root_dir
        self._cached_for: ComicBook | None = None
        self._cached: tuple[SrceAndDestPages, RequiredDimensions] | None = None

    def get_sorted_pages(self, comic: ComicBook) -> SrceAndDestPages:
        return self._load(comic)[0]

    def get_required_dimensions(self, comic: ComicBook) -> RequiredDimensions:
        return self._load(comic)[1]

    def _load(self, comic: ComicBook) -> tuple[SrceAndDestPages, RequiredDimensions]:
        if self._cached_for is not comic or self._cached is None:
            vol_title = self._comics_database.get_fantagraphics_volume_title(
                comic.get_fanta_volume()
            )
            panel_segments_dir = self._panel_segments_root_dir / vol_title

            def get_srce_panel_segments_file(page_num: str) -> Path:
                return panel_segments_dir / (page_num + JSON_FILE_EXT)

            srce_and_dest_pages, _srce_dim, required_dim = (
                get_sorted_srce_and_dest_pages_with_dimensions(
                    comic,
                    get_full_paths=False,
                    get_srce_panel_segments_file=get_srce_panel_segments_file,
                    check_srce_page_timestamps=False,
                )
            )
            self._cached_for = comic
            self._cached = (srce_and_dest_pages, required_dim)
        return self._cached
