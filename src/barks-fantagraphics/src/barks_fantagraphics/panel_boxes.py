import json
from dataclasses import dataclass
from pathlib import Path

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import ComicBook, get_page_str
from barks_fantagraphics.comics_consts import RESTORABLE_PAGE_TYPES
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.pages import get_sorted_srce_and_dest_pages


@dataclass(frozen=True, slots=True)
class PanelBox:
    panel_num: int
    x0: int
    y0: int
    x1: int
    y1: int
    w: int
    h: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return self.x0, self.y0, self.x1, self.y1


@dataclass(frozen=True, slots=True)
class PagePanelBoxes:
    page_num: str
    page_width: int
    page_height: int
    panel_boxes: list[PanelBox]


@dataclass(frozen=True, slots=True)
class TitlePagesPanelBoxes:
    title: Titles
    title_str: str
    volume: int
    pages: dict[str, PagePanelBoxes]


@dataclass(frozen=True, slots=True)
class TitlePanelBoxes:
    _comics_database: ComicsDatabase

    def get_page_panel_boxes(self, title: Titles) -> TitlePagesPanelBoxes:
        title_str = BARKS_TITLES[title]

        volume = self._comics_database.get_fanta_volume_int(title_str)
        comic = self._comics_database.get_comic_book(title_str)

        pages = {
            page_num: self._get_panel_boxes(comic, page_num)
            for page_num in self._get_srce_page_nums(comic)
        }

        return TitlePagesPanelBoxes(title, title_str, volume, pages)

    @staticmethod
    def get_panel_boxes(panel_segments_file: Path, page_num: str) -> PagePanelBoxes:
        if not panel_segments_file.is_file():
            msg = f'Could not find panel segments file "{panel_segments_file}".'
            raise FileNotFoundError(msg)
        panel_segments = json.loads(panel_segments_file.read_text())

        page_width = panel_segments["size"][0]
        page_height = panel_segments["size"][1]
        panel_boxes: list[PanelBox] = []
        for i, panel in enumerate(panel_segments["panels"]):
            x0 = panel[0]
            y0 = panel[1]
            w = panel[2]
            h = panel[3]
            x1 = x0 + w - 1
            y1 = y0 + h - 1
            panel_box = PanelBox(i + 1, x0, y0, x1, y1, w, h)
            panel_boxes.append(panel_box)

        return PagePanelBoxes(page_num, page_width, page_height, panel_boxes)

    def _get_panel_boxes(self, comic: ComicBook, page_num: str) -> PagePanelBoxes:
        panel_segments_file = comic.get_srce_panel_segments_file(page_num)
        return self.get_panel_boxes(panel_segments_file, page_num)

    @staticmethod
    def _get_srce_page_nums(comic: ComicBook) -> list[str]:
        return [
            get_page_str(srce_page.page_num)
            for srce_page in get_sorted_srce_and_dest_pages(comic, get_full_paths=True).srce_pages
            if srce_page.page_type in RESTORABLE_PAGE_TYPES
        ]
